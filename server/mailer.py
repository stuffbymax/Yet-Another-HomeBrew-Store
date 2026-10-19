"""Tiny SMTP mailer. In development with no MAIL_SERVER the message is printed instead of sent."""
import logging
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("yahbs.mail")


def send_mail(cfg, to, subject, body):
    if not cfg["MAIL_SERVER"]:
        if cfg["ENV_NAME"] == "development":
            print(f"\n--- MAIL to {to} ---\n{subject}\n{body}\n---", flush=True)  # dev only: contains tokens
        else:
            log.error("MAIL_SERVER not configured; cannot send mail to %s", to)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_FROM"], to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            if cfg["MAIL_USERNAME"]:
                s.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            s.send_message(msg)
        return True
    except Exception:
        log.exception("mail send failed")
        return False
