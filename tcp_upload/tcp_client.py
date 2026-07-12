"""
TCP Client Helper
==================
Dipakai oleh route /upload di Flask (app.py) untuk mengirim file
ke TCP server (tcp_server.py) menggunakan socket TCP asli.
"""
import os
import socket
import struct
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


def send_file_via_tcp(filepath, original_filename=None, host=None, port=None, timeout=30):
    host = host or Config.TCP_HOST
    port = port or Config.TCP_PORT
    original_filename = original_filename or os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))

        name_bytes = original_filename.encode("utf-8")
        s.sendall(struct.pack("!I", len(name_bytes)))
        s.sendall(name_bytes)
        s.sendall(struct.pack("!Q", filesize))

        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                s.sendall(chunk)

        response = s.recv(1024).decode("utf-8", errors="ignore")
        return response, filesize
