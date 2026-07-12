"""
TCP File Upload Server
=======================
Server socket TCP murni yang menerima file dari client (Flask app bertindak
sebagai TCP client lewat tcp_client.py).

Protokol sederhana (custom, di atas TCP):
    [4 byte]  panjang nama file      (big-endian unsigned int)
    [N byte]  nama file              (utf-8)
    [8 byte]  ukuran file            (big-endian unsigned long long)
    [ukuran file byte] isi file (binary)

Balasan server: "OK" / "INCOMPLETE" / "ERROR"

Jalankan terpisah:
    python tcp_upload/tcp_server.py
"""
import os
import socket
import struct
import sys
import threading
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


def recv_exact(conn, n):
    """Baca persis n byte dari socket (menangani partial recv TCP)."""
    data = b""
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            raise ConnectionError("Koneksi terputus saat menerima data")
        data += packet
    return data


def handle_client(conn, addr):
    print(f"[TCP] Koneksi masuk dari {addr}")
    try:
        raw_len = recv_exact(conn, 4)
        name_len = struct.unpack("!I", raw_len)[0]
        filename = recv_exact(conn, name_len).decode("utf-8")

        raw_size = recv_exact(conn, 8)
        filesize = struct.unpack("!Q", raw_size)[0]

        safe_name = os.path.basename(filename)
        # Beri prefix unik supaya file dengan nama sama dari user berbeda tidak saling menimpa
        stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        save_path = os.path.join(Config.UPLOAD_FOLDER, stored_name)

        received = 0
        with open(save_path, "wb") as f:
            while received < filesize:
                chunk = conn.recv(min(65536, filesize - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)

        status = "OK" if received == filesize else "INCOMPLETE"
        # Format response: STATUS|nama_file_tersimpan
        response = f"{status}|{stored_name}"
        conn.sendall(response.encode("utf-8"))
        print(f"[TCP] File '{safe_name}' diterima sebagai '{stored_name}' ({received}/{filesize} byte) -> {status}")
    except Exception as e:
        print("[TCP] Error saat menerima file:", e)
        try:
            conn.sendall(b"ERROR")
        except Exception:
            pass
    finally:
        conn.close()


def start_server(host=None, port=None):
    host = host or Config.TCP_HOST
    port = port or Config.TCP_PORT

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    print(f"[TCP] Server upload berjalan di {host}:{port}")
    print(f"[TCP] File akan disimpan di: {Config.UPLOAD_FOLDER}")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[TCP] Server dihentikan")
    finally:
        server.close()


if __name__ == "__main__":
    start_server()
