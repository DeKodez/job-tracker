"""Email notification for job tracker using SMTP (Gmail, SendGrid, etc.)."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email_digest(subject: str, body: str) -> None:
    """Send an email with the job digest.

    Configure via environment variables:
      SMTP_HOST      (default: smtp.gmail.com)
      SMTP_PORT      (default: 587)
      SMTP_USER      (your email / API key)
      SMTP_PASS      (app password or API key)
      SMTP_TO        (recipient, comma-separated)
    """
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    to_addr = os.environ.get("SMTP_TO", user)

    if not user or not password:
        raise RuntimeError("SMTP_USER and SMTP_PASS must be set in environment")

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, to_addr.split(","), msg.as_string())

    print(f"Email sent to {to_addr}")
