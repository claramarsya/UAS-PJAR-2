"""
UDP Video Streaming Receiver
==============================
Menerima frame JPEG melalui socket UDP dari udp_sender.py, lalu
frame tersebut di-'jembatani' oleh Flask (route /video_feed di app.py)
menjadi MJPEG stream (multipart/x-mixed-replace) supaya bisa
ditampilkan langsung di tag <img> pada browser.

(Catatan: browser tidak bisa membaca socket UDP secara langsung,
sehingga Flask bertindak sebagai UDP receiver + jembatan ke HTTP
untuk keperluan tampilan di web, sedangkan transport data video
antar proses sender -> receiver murni menggunakan protokol UDP.)

PENTING: hanya ada SATU socket receiver yang berjalan di thread latar
belakang, menyimpan frame terakhir. Semua permintaan /video_feed membaca
frame yang sama. Ini mencegah bug lama di mana setiap request membuka
socket UDP baru pada port yang sama -> frame terbagi antar socket dan
tampilan jadi berkedip/menumpuk saat halaman di-reload atau ganti video.
"""
import os
import socket
import sys
import threading
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

_latest_frame = None
_lock = threading.Lock()
_listener_started = False
_start_lock = threading.Lock()


def _listen(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    print(f"[UDP] Receiver mendengarkan di {host}:{port}")

    global _latest_frame
    while True:
        try:
            data, _addr = sock.recvfrom(65536)
        except OSError:
            continue
        if data:
            with _lock:
                _latest_frame = data


def _ensure_listener(host, port):
    """Jalankan thread receiver sekali saja (idempotent, aman dari race)."""
    global _listener_started
    with _start_lock:
        if _listener_started:
            return
        _listener_started = True
        threading.Thread(target=_listen, args=(host, port), daemon=True).start()


def frame_generator(host=None, port=None):
    host = host or Config.UDP_HOST
    port = port or Config.UDP_PORT
    _ensure_listener(host, port)

    while True:
        with _lock:
            frame = _latest_frame
        if frame is not None:
            # Content-Length membuat browser tahu persis batas tiap frame,
            # sehingga tidak mengira-ira dan tampilan tidak berkedip.
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                   + frame + b"\r\n")
        time.sleep(1 / 20)  # relay ~20 fps, samakan dengan sender
