import io, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pathlib import Path
import pytest
from PIL import Image

os.environ["YAHBS_ENV"] = "development"


@pytest.fixture()
def client():
    from app import create_app
    from extensions import limiter
    tmp = Path(tempfile.mkdtemp())
    import signing
    seed, _ = signing.generate()
    app = create_app({"TESTING": True, "SIGNING_KEY_HEX": seed, "UPLOAD_DIR": tmp / "up", "RATELIMIT_ENABLED": False,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp/'t.db'}",
                      "WTF_CSRF_ENABLED": False, "SESSION_COOKIE_SECURE": False})
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    limiter.enabled = False
    with app.test_client() as c:
        c.app = app
        yield c


def signup(c, name="alice", email=None, pw="correct horse battery", verified=True):
    c.post("/register", data={"username": name, "email": email or f"{name}@example.com",
                              "password": pw, "confirm": pw, "accept": "y"})
    if verified:
        from extensions import db
        from models import User
        with c.application.app_context():
            User.query.filter_by(username=name).one().email_verified = True; db.session.commit()
    return c.post("/login", data={"username": name, "password": pw})


def upload(c, name="Demo", platform="ps4", body=b"\x7fCNT" + b"x" * 100, fn="demo.pkg"):
    png = io.BytesIO(); Image.new("RGB", (64, 64), "red").save(png, "PNG"); png.seek(0)
    return c.post("/dashboard/new", data={
        "name": name, "platform": platform, "version": "1.0", "short_desc": "s", "description": "d",
        "accept": "y", "package": (io.BytesIO(body), fn), "icon": (png, "i.png")},
        content_type="multipart/form-data")


def test_flow_and_moderation(client):
    signup(client)
    assert upload(client).status_code == 302
    assert b"Demo" not in client.get("/").data               # pending => hidden
    assert client.get("/api/v1/catalog.tsv").status_code == 400      # platform required (signed per platform)
    assert client.get("/app/1/download").status_code == 200  # owner can fetch own
    from extensions import db
    from models import HomebrewApp, User
    with client.application.app_context():
        HomebrewApp.query.get(1).status = "approved"; db.session.commit()
    assert b"Demo" in client.get("/").data
    rows = [l for l in client.get("/api/v1/catalog.tsv?platform=ps4").data.decode().splitlines() if not l.startswith("#")]
    line = rows[0].split("\t")
    assert line[1] == "Demo" and len(line[5]) == 64 and line[6] == "pkg"
    r = client.get("/app/1/download")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and "attachment" in r.headers["Content-Disposition"]


def test_bad_uploads_rejected(client):
    signup(client)
    assert upload(client, body=b"MZ evil", fn="a.pkg").status_code == 200       # wrong magic
    assert upload(client, body=b"\x7fCNT" + b"x" * 9, fn="a.exe").status_code == 200  # bad ext
    assert upload(client, platform="ps3", body=b"\x7fELF" + b"x" * 9, fn="a.elf").status_code == 200  # elf not for ps3
    assert upload(client, body=b"\x7fCNT" + b"x" * 9, fn="../../etc/passwd.pkg").status_code == 302  # name is ignored, stored as uuid
    from models import HomebrewApp
    with client.application.app_context():
        assert HomebrewApp.query.count() == 1
        assert re.fullmatch(r"[0-9a-f]{32}\.pkg", HomebrewApp.query.first().package_file)


def test_idor_and_admin(client):
    signup(client); upload(client)
    client.post("/logout")
    signup(client, "bob")
    assert client.get("/dashboard/1/edit").status_code == 404
    assert client.post("/dashboard/1/delete").status_code == 404
    assert client.get("/admin").status_code == 404
    assert client.get("/app/1").status_code == 404           # pending, not owner


def test_login_lockout_and_open_redirect(client):
    signup(client, "carol"); client.post("/logout")
    for _ in range(5):
        client.post("/login", data={"username": "carol", "password": "wrong-wrong-wrong"})
    r = client.post("/login", data={"username": "carol", "password": "correct horse battery"})
    assert r.status_code == 200                              # locked even with right password
    client.post("/logout")
    signup(client, "dave")
    client.post("/logout")
    r = client.post("/login?next=https://evil.example/", data={"username": "dave", "password": "correct horse battery"})
    assert "evil.example" not in r.headers["Location"]


def test_csp_and_xss(client):
    signup(client)
    upload(client, name="<script>alert(1)</script>")
    r = client.get("/dashboard")
    assert b"<script>alert(1)</script>" not in r.data
    assert "script-src 'self'" in client.get("/").headers["Content-Security-Policy"]


# ---------------- new features ----------------
def capture_mail(monkeypatch):
    sent = []
    import account
    monkeypatch.setattr(account, "send_mail", lambda cfg, to, subj, body: sent.append((to, subj, body)))
    return sent


def test_email_verification_gates_upload(client, monkeypatch):
    sent = capture_mail(monkeypatch)
    signup(client, "erin", verified=False)
    assert upload(client).status_code == 302                  # redirected to dashboard, nothing stored
    from models import HomebrewApp
    with client.application.app_context():
        assert HomebrewApp.query.count() == 0
    token = re.search(r"/verify/(\S+)", sent[0][2]).group(1)
    assert client.get("/verify/" + token + "x").status_code == 302   # tampered token => error flash only
    client.get("/verify/" + token)
    assert upload(client).status_code == 302
    with client.application.app_context():
        assert HomebrewApp.query.count() == 1


def test_password_reset_single_use(client, monkeypatch):
    sent = capture_mail(monkeypatch)
    signup(client, "frank"); client.post("/logout"); sent.clear()
    client.post("/forgot", data={"email": "nobody@example.com"})
    assert sent == []                                          # no leak, no mail for unknown address
    client.post("/forgot", data={"email": "frank@example.com"})
    tok = re.search(r"/reset/(\S+)", sent[0][2]).group(1)
    new = "a brand new passphrase"
    assert client.post("/reset/" + tok, data={"password": new, "confirm": new}).status_code == 302
    assert client.post("/login", data={"username": "frank", "password": new}).status_code == 302
    client.post("/logout")
    r = client.post("/reset/" + tok, data={"password": "another passphrase!!", "confirm": "another passphrase!!"})
    assert r.status_code == 302 and "/forgot" in r.headers["Location"]   # reused link rejected


def test_totp_login_and_admin_gate(client):
    import totp
    from extensions import db
    from models import User
    signup(client, "root")
    with client.application.app_context():
        u = User.query.filter_by(username="root").one(); u.role = "admin"; db.session.commit()
    assert "/account/2fa" in client.get("/admin").headers["Location"]      # admin without 2FA is bounced
    client.get("/account/2fa")
    with client.application.app_context():
        secret = totp.decrypt(client.application.config["SECRET_KEY"], User.query.filter_by(username="root").one().totp_secret)
    assert client.post("/account/2fa", data={"code": "000000"}).status_code == 200      # wrong code
    assert client.post("/account/2fa", data={"code": totp._code(secret, int(__import__("time").time() // 30))}).status_code == 302
    assert client.get("/admin").status_code == 200
    client.post("/logout")
    r = client.post("/login", data={"username": "root", "password": "correct horse battery"})
    assert "/login/2fa" in r.headers["Location"]
    assert client.get("/admin").status_code in (302, 404)                   # not logged in yet
    assert client.post("/login/2fa", data={"code": "123456"}).status_code in (200, 302)
    with client.application.app_context():
        last = User.query.filter_by(username="root").one().totp_last_step
    good = totp._code(secret, int(__import__("time").time() // 30) + 1)     # next window, accepted once
    assert client.post("/login/2fa", data={"code": good}).status_code == 302
    client.post("/logout"); client.post("/login", data={"username": "root", "password": "correct horse battery"})
    client.post("/login/2fa", data={"code": good})                          # replay must fail
    assert client.get("/admin").status_code in (302, 404)


def test_totp_rfc6238_vector():
    import base64, totp
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp._code(secret, 59 // 30) == "287082"            # RFC 6238 test vector (last 6 of 94287082)


def test_report_and_takedown(client):
    signup(client, "gina"); upload(client)
    from extensions import db
    from models import HomebrewApp, User
    with client.application.app_context():
        HomebrewApp.query.get(1).status = "approved"; db.session.commit()
    client.post("/logout"); signup(client, "hank")
    client.post("/app/1/report", data={"reason": "this looks like a pirated game dump"})
    from models import Report
    with client.application.app_context():
        assert Report.query.count() == 1
    assert client.post("/app/1/report", data={"reason": "short"}).status_code == 302
    with client.application.app_context():
        assert Report.query.count() == 1


def test_signature_verifies_and_detects_tampering(client):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.exceptions import InvalidSignature
    import signing
    seed, pub = signing.generate()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    text = signing.sign_catalog(seed, "ps4", ["1\tA\t1.0\tps4\t10\t" + "a" * 64], now=1)
    body, sigline = text.rsplit("#sig\t", 1)
    Ed25519PublicKey.from_public_bytes(pub).verify(bytes.fromhex(sigline.strip()), body.encode())
    with pytest.raises(InvalidSignature):
        Ed25519PublicKey.from_public_bytes(pub).verify(bytes.fromhex(sigline.strip()), body.replace("10", "11").encode())


def test_clamd_fail_closed_and_found():
    import socket, struct, threading, tempfile
    from scan import scan_file
    from security import UploadError
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port = srv.getsockname()[1]
    def serve(reply):
        c, _ = srv.accept()
        while True:                                     # read until zero-length chunk
            buf = c.recv(10) if False else b""
            break
        c.settimeout(2)
        try:
            while c.recv(65536): pass
        except OSError: pass
        c.sendall(reply); c.close()
    f = tempfile.NamedTemporaryFile(delete=False); f.write(b"x" * 100); f.close()
    # clean file
    t = threading.Thread(target=serve, args=(b"stream: OK\0",)); t.start()
    scan_file(f.name, f"127.0.0.1:{port}"); t.join()
    # infected
    t = threading.Thread(target=serve, args=(b"stream: Eicar-Test-Signature FOUND\0",)); t.start()
    with pytest.raises(UploadError):
        scan_file(f.name, f"127.0.0.1:{port}")
    t.join(); srv.close()
    with pytest.raises(UploadError):                    # scanner down => reject
        scan_file(f.name, f"127.0.0.1:{port}")
