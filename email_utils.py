import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(config, to_email, subject, html_body):
    """Kirim email via SMTP. Jika kredensial SMTP belum diatur di .env,
    email akan ditampilkan di console server (mode development)."""
    if not config.MAIL_USERNAME or not config.MAIL_PASSWORD:
        print(f"[EMAIL-DEV] SMTP belum dikonfigurasi. To: {to_email} | Subject: {subject}")
        print(html_body)
        return False, "SMTP belum dikonfigurasi (.env). Email hanya ditampilkan di console server."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.MAIL_DEFAULT_SENDER
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT) as server:
            server.ehlo()
            if config.MAIL_USE_TLS:
                server.starttls(context=context)
                server.ehlo()
            server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
            server.sendmail(config.MAIL_DEFAULT_SENDER, to_email, msg.as_string())
        return True, "Email terkirim"
    except Exception as e:
        print("Gagal mengirim email:", e)
        return False, str(e)


def verification_email_body(name, verify_link):
    return f"""
    <div style="font-family: Arial, sans-serif; max-width:480px; margin:auto;">
      <h2>Verifikasi Akun Anda</h2>
      <p>Halo <b>{name}</b>,</p>
      <p>Terima kasih telah mendaftar di aplikasi UAS Pemrograman Jaringan.
      Silakan klik tombol di bawah untuk memverifikasi akun Anda:</p>
      <p>
        <a href="{verify_link}"
           style="background:#2563eb;color:#fff;padding:10px 20px;
           text-decoration:none;border-radius:6px;display:inline-block;">
           Verifikasi Akun
        </a>
      </p>
      <p>Atau salin tautan berikut ke browser Anda:<br>{verify_link}</p>
    </div>
    """


def login_notification_body(name, login_time, ip_address):
    return f"""
    <div style="font-family: Arial, sans-serif; max-width:480px; margin:auto;">
      <h2>Notifikasi Login</h2>
      <p>Halo <b>{name}</b>,</p>
      <p>Akun Anda baru saja login pada <b>{login_time}</b> dari alamat IP <b>{ip_address}</b>.</p>
      <p>Jika ini bukan Anda, segera ganti password Anda.</p>
    </div>
    """
