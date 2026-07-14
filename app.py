import atexit
import glob
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash, Response,
    send_from_directory, abort,
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from config import Config, BASE_DIR
from models import db, User, UploadedFile
from email_utils import send_email, verification_email_body, login_notification_body
from tcp_upload.tcp_client import send_file_via_tcp
from udp_stream.udp_receiver import frame_generator

ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Menyimpan proses udp_sender.py yang sedang berjalan, supaya bisa diganti videonya
_udp_sender_state = {"process": None, "video": None}


def _list_media_videos():
    """Daftar semua video yang ada di folder media/."""
    media_dir = os.path.join(BASE_DIR, "media")
    os.makedirs(media_dir, exist_ok=True)
    videos = []
    for path in sorted(glob.glob(os.path.join(media_dir, "*"))):
        if os.path.splitext(path)[1].lower() in ALLOWED_VIDEO_EXT:
            videos.append(os.path.basename(path))
    return videos


def _start_udp_sender(video_filename):
    """Hentikan udp_sender.py yang sedang berjalan (jika ada), lalu jalankan
    ulang dengan video yang baru dipilih."""
    media_dir = os.path.join(BASE_DIR, "media")
    video_path = os.path.join(media_dir, video_filename)
    if not os.path.isfile(video_path):
        return False, "File video tidak ditemukan."

    # Hentikan proses sender lama
    old_proc = _udp_sender_state.get("process")
    if old_proc and old_proc.poll() is None:
        old_proc.terminate()
        try:
            old_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            old_proc.kill()

    sender_script = os.path.join(BASE_DIR, "udp_stream", "udp_sender.py")
    new_proc = subprocess.Popen(
        [sys.executable, sender_script, video_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _udp_sender_state["process"] = new_proc
    _udp_sender_state["video"] = video_filename
    return True, "Video streaming berhasil diganti."


@atexit.register
def _cleanup_udp_sender():
    proc = _udp_sender_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message = "Silakan login terlebih dahulu."
    login_manager.init_app(app)

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    with app.app_context():
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ---------------- ROUTES ----------------

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not name or not email or not password:
                flash("Semua field wajib diisi.", "error")
                return redirect(url_for("register"))

            if User.query.filter_by(email=email).first():
                flash("Email sudah terdaftar.", "error")
                return redirect(url_for("register"))

            token = uuid.uuid4().hex
            user = User(name=name, email=email, is_verified=False, verification_token=token)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # _external=True membuat link absolut dari domain yang sedang diakses,
            # jadi otomatis benar baik saat lokal maupun setelah deploy (Cloudflare).
            verify_link = url_for("verify_email", token=token, _external=True)
            ok, info = send_email(
                Config, email, "Verifikasi Akun - UAS Pemrograman Jaringan",
                verification_email_body(name, verify_link),
            )
            if ok:
                flash("Registrasi berhasil. Silakan cek email Anda untuk verifikasi akun.", "success")
            else:
                flash(
                    f"Registrasi berhasil, namun email gagal terkirim ({info}). "
                    f"Cek console server untuk melihat link verifikasi.",
                    "warning",
                )

            return redirect(url_for("verify_pending", email=email))

        return render_template("register.html")

    @app.route("/verify-pending")
    def verify_pending():
        email = request.args.get("email", "")
        return render_template("verify_pending.html", email=email)

    @app.route("/verify/<token>")
    def verify_email(token):
        user = User.query.filter_by(verification_token=token).first()
        if not user:
            flash("Tautan verifikasi tidak valid atau sudah digunakan.", "error")
            return redirect(url_for("login"))

        user.is_verified = True
        user.verification_token = None
        db.session.commit()
        flash("Akun berhasil diverifikasi. Silakan login.", "success")
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if not user or not user.check_password(password):
                flash("Email atau password salah.", "error")
                return redirect(url_for("login"))

            if not user.is_verified:
                flash("Akun belum diverifikasi. Silakan cek email Anda terlebih dahulu.", "error")
                return redirect(url_for("login"))

            login_user(user)

            login_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            ip_address = request.remote_addr
            send_email(
                Config, user.email, "Notifikasi Login - UAS Pemrograman Jaringan",
                login_notification_body(user.name, login_time, ip_address),
            )

            flash("Login berhasil. Email notifikasi login telah dikirim.", "success")
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Anda telah logout.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        files = (
            UploadedFile.query.filter_by(user_id=current_user.id)
            .order_by(UploadedFile.uploaded_at.desc())
            .all()
        )
        return render_template("dashboard.html", files=files)

    @app.route("/upload", methods=["GET", "POST"])
    @login_required
    def upload():
        if request.method == "POST":
            file = request.files.get("file")
            if not file or file.filename == "":
                flash("Pilih file terlebih dahulu.", "error")
                return redirect(url_for("upload"))

            filename = file.filename
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            try:
                response, filesize = send_file_via_tcp(tmp_path, original_filename=filename)
            except Exception as e:
                flash(f"Gagal mengirim file via TCP: {e}. Pastikan TCP server (tcp_server.py) berjalan.", "error")
                os.remove(tmp_path)
                return redirect(url_for("upload"))

            os.remove(tmp_path)

            # Response dari TCP server berformat "STATUS|nama_file_tersimpan"
            parts = response.split("|", 1)
            status = parts[0]
            stored_name = parts[1] if len(parts) > 1 else filename

            if status == "OK":
                record = UploadedFile(
                    user_id=current_user.id,
                    filename=filename,
                    stored_filename=stored_name,
                    filesize=filesize,
                )
                db.session.add(record)
                db.session.commit()
                flash(f"File '{filename}' berhasil diupload via TCP ({filesize} byte).", "success")
            else:
                flash(f"Upload gagal, response dari TCP server: {response}", "error")

            return redirect(url_for("upload"))

        files = (
            UploadedFile.query.filter_by(user_id=current_user.id)
            .order_by(UploadedFile.uploaded_at.desc())
            .all()
        )
        return render_template("upload.html", files=files)

    @app.route("/files/download/<int:file_id>")
    @login_required
    def download_file(file_id):
        record = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first()
        if not record:
            abort(404)
        return send_from_directory(
            Config.UPLOAD_FOLDER, record.stored_filename,
            as_attachment=True, download_name=record.filename,
        )

    @app.route("/files/delete/<int:file_id>", methods=["POST"])
    @login_required
    def delete_file(file_id):
        record = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first()
        if not record:
            abort(404)
        physical_path = os.path.join(Config.UPLOAD_FOLDER, record.stored_filename)
        try:
            if os.path.isfile(physical_path):
                os.remove(physical_path)
        except OSError:
            pass
        db.session.delete(record)
        db.session.commit()
        flash(f"File '{record.filename}' berhasil dihapus.", "success")
        return redirect(request.referrer or url_for("dashboard"))

    @app.route("/stream")
    @login_required
    def stream():
        videos = _list_media_videos()
        current_video = _udp_sender_state.get("video")
        return render_template("stream.html", videos=videos, current_video=current_video)

    @app.route("/stream/upload", methods=["POST"])
    @login_required
    def stream_upload_video():
        file = request.files.get("video_file")
        if not file or file.filename == "":
            flash("Pilih file video terlebih dahulu.", "error")
            return redirect(url_for("stream"))

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_VIDEO_EXT:
            flash(f"Format video tidak didukung ({ext}). Gunakan: {', '.join(ALLOWED_VIDEO_EXT)}", "error")
            return redirect(url_for("stream"))

        safe_name = secure_filename(file.filename)
        media_dir = os.path.join(BASE_DIR, "media")
        os.makedirs(media_dir, exist_ok=True)
        save_path = os.path.join(media_dir, safe_name)
        file.save(save_path)

        ok, info = _start_udp_sender(safe_name)
        if ok:
            flash(f"Video '{safe_name}' berhasil diupload dan sedang di-stream.", "success")
        else:
            flash(f"Video tersimpan, tapi gagal memulai streaming: {info}", "warning")

        return redirect(url_for("stream"))

    @app.route("/stream/select", methods=["POST"])
    @login_required
    def stream_select_video():
        video_filename = request.form.get("video_filename")
        if not video_filename:
            flash("Pilih video terlebih dahulu.", "error")
            return redirect(url_for("stream"))

        ok, info = _start_udp_sender(video_filename)
        if ok:
            flash(f"Sekarang streaming video: {video_filename}", "success")
        else:
            flash(f"Gagal mengganti video: {info}", "error")

        return redirect(url_for("stream"))

    @app.route("/video_feed")
    @login_required
    def video_feed():
        return Response(
            frame_generator(), mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    # Jalankan udp_sender.py otomatis dengan video default (jika ada), saat app start.
    # Cek WERKZEUG_RUN_MAIN supaya tidak dobel proses saat Flask debug reloader aktif.
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        default_videos = _list_media_videos()
        if default_videos:
            _start_udp_sender(default_videos[0])

    return app


app = create_app()

if __name__ == "__main__":
    # use_reloader=False: matikan auto-reload Flask. Reloader bisa restart aplikasi
    # sendiri lalu memulai ulang sender video "default", sementara sender video yang
    # sedang dipilih jadi proses yatim -> video lama (mis. ghibli) muncul-hilang.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
