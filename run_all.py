"""
Script bantuan untuk menjalankan ketiga service sekaligus saat demo lokal:
1. TCP server (tcp_upload/tcp_server.py)
2. UDP sender  (udp_stream/udp_sender.py)
3. Flask web app (app.py)

Jalankan:
    python run_all.py

Tekan Ctrl+C untuk menghentikan semuanya.
"""
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    procs = []
    print("Menjalankan TCP server...")
    procs.append(subprocess.Popen([sys.executable, os.path.join(BASE, "tcp_upload", "tcp_server.py")]))

    time.sleep(1)

    # Catatan: UDP sender TIDAK dijalankan manual di sini lagi.
    # Flask app (app.py) akan otomatis menjalankan/mengganti udp_sender.py
    # sesuai video yang dipilih user di halaman /stream.
    print("Menjalankan Flask web app (otomatis mengelola UDP sender)...")
    procs.append(subprocess.Popen([sys.executable, os.path.join(BASE, "app.py")]))

    print("\nSemua service berjalan:")
    print(" - Web app     : http://127.0.0.1:5000")
    print(" - TCP server  : lihat log di atas")
    print(" - UDP sender  : dikelola otomatis lewat halaman /stream")
    print("\nTekan Ctrl+C untuk menghentikan semua service.\n")

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\nMenghentikan semua service...")
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
