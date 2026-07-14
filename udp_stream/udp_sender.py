"""
UDP Video Streaming Sender
===========================
Membaca file video (atau webcam) lalu mengirim tiap frame sebagai
JPEG melalui socket UDP ke udp_receiver.py.

Jalankan terpisah:
    python udp_stream/udp_sender.py
"""
import os
import socket
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

try:
    import cv2
except ImportError:
    cv2 = None

MAX_DGRAM = 60000       # aman di bawah batas datagram UDP (65507 byte)
TARGET_MAX_WIDTH = 480  # lebar maksimum frame yang dikirim
JPEG_QUALITY = 50       # kualitas TETAP: pada lebar 480, frame selalu muat 1 datagram,
                        # jadi kualitas tidak berubah-ubah (menghindari kedip tajam<->buram)
FPS = 20


def resize_keep_aspect_ratio(frame, max_width=TARGET_MAX_WIDTH):
    """Resize frame TANPA mengubah rasio aspek aslinya (tidak gepeng).
    Tinggi dihitung otomatis mengikuti rasio lebar:tinggi video asli."""
    h, w = frame.shape[:2]
    if w == 0 or h == 0:
        return frame
    if w <= max_width:
        return frame  # sudah cukup kecil, tidak perlu resize
    scale = max_width / float(w)
    new_w = max_width
    new_h = int(round(h * scale))
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def start_sender(video_source=None, host=None, port=None, loop=True):
    if cv2 is None:
        print("OpenCV belum terinstall. Jalankan: pip install opencv-python-headless")
        return

    video_source = video_source or Config.VIDEO_SOURCE
    host = host or Config.UDP_HOST
    port = port or Config.UDP_PORT

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    use_webcam = str(video_source) == "0"
    cap = cv2.VideoCapture(0 if use_webcam else video_source)
    if not cap.isOpened():
        print(f"[UDP] Tidak bisa membuka sumber video: {video_source}")
        print("[UDP] Pastikan file video ada di folder media/, atau set VIDEO_SOURCE=0 untuk webcam.")
        return

    print(f"[UDP] Streaming ke {host}:{port} dari sumber '{video_source}'")

    delay = 1.0 / FPS
    next_frame_at = time.perf_counter()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                if loop and not use_webcam:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    next_frame_at = time.perf_counter()
                    continue
                else:
                    break

            frame = resize_keep_aspect_ratio(frame)
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                data = encoded.tobytes()
                if len(data) <= MAX_DGRAM:
                    sock.sendto(data, (host, port))
                # kalau > MAX_DGRAM (sangat jarang di lebar 480): frame ini dilewati
                # saja. Penerima tetap menampilkan frame terakhir, jadi tidak berkedip.

            # Pacing berbasis jam supaya tempo stabil (bukan sleep tetap yang
            # menumpuk waktu encode -> jadinya patah/tersendat).
            next_frame_at += delay
            wait = next_frame_at - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            else:
                next_frame_at = time.perf_counter()
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        sock.close()
        print("[UDP] Sender dihentikan")


if __name__ == "__main__":
    # Bisa dipanggil dengan: python udp_sender.py <path_video>
    # supaya Flask app bisa mengganti video streaming tanpa restart manual.
    override_source = sys.argv[1] if len(sys.argv) > 1 else None
    start_sender(video_source=override_source)
