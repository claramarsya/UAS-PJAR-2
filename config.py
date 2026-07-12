import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "ganti-secret-key-ini")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- Email (SMTP) ----
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    # URL dasar aplikasi (dipakai untuk membuat link verifikasi email)
    # Saat deploy via Cloudflare, ganti dengan domain Cloudflare kamu, mis:
    # BASE_URL=https://uas-jarkom.namakamu.workers.dev  atau domain tunnel cloudflared
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")

    # ---- TCP File Upload Server ----
    TCP_HOST = os.environ.get("TCP_HOST", "127.0.0.1")
    TCP_PORT = int(os.environ.get("TCP_PORT", 9001))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

    # ---- UDP Video Streaming ----
    UDP_HOST = os.environ.get("UDP_HOST", "127.0.0.1")
    UDP_PORT = int(os.environ.get("UDP_PORT", 9002))
    # Bisa diisi path file video, atau "0" untuk pakai webcam
    VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", os.path.join(BASE_DIR, "media", "sample.mp4"))
