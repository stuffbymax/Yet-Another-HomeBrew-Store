"""RFC 6238 TOTP (SHA-1, 6 digits, 30 s) using only the standard library + Fernet for storage."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken


def _fernet(app_secret):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"yahbs-totp|" + app_secret.encode()).digest()))


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode()


def encrypt(app_secret, secret):
    return _fernet(app_secret).encrypt(secret.encode()).decode()


def decrypt(app_secret, token):
    try:
        return _fernet(app_secret).decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def _code(secret, step):
    h = hmac.new(base64.b32decode(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    o = h[-1] & 15
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % 10**6:06d}"


def verify(secret, code, last_step, now=None):
    """Returns the matched time step (store it to block replay) or None."""
    step_now = int((now if now is not None else time.time()) // 30)
    for step in (step_now - 1, step_now, step_now + 1):
        if step > last_step and hmac.compare_digest(_code(secret, step), code):
            return step
    return None


def uri(secret, username):
    return f"otpauth://totp/YAHBS:{quote(username)}?secret={secret}&issuer=YAHBS"
