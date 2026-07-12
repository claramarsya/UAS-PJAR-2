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
"""
import os
import socket
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


def frame_generator(host=None, port=None, timeout=5):
    host = host or Config.UDP_HOST
    port = port or Config.UDP_PORT

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.bind((host, port))
    print(f"[UDP] Receiver mendengarkan di {host}:{port}")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(65536)
            except socket.timeout:
                continue
            if not data:
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
    finally:
        sock.close()
