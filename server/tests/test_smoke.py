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
    app = create_app({"TESTING": True, "UPLOAD_DIR": tmp / "up", "RATELIMIT_ENABLED": False,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp/'t.db'}",
                      "WTF_CSRF_ENABLED": False, "SESSION_COOKIE_SECURE": False})
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    limiter.enabled = False
    with app.test_client() as c:
        c.app = app
        yield c


def signup(c, name="alice", email=None, pw="correct horse battery"):
    c.post("/register", data={"username": name, "email": email or f"{name}@example.com",
                              "password": pw, "confirm": pw, "accept": "y"})
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
    assert client.get("/api/v1/catalog.tsv").data.strip() == b""
    assert client.get("/app/1/download").status_code == 200  # owner can fetch own
    from extensions import db
    from models import HomebrewApp, User
    with client.application.app_context():
        HomebrewApp.query.get(1).status = "approved"; db.session.commit()
    assert b"Demo" in client.get("/").data
    line = client.get("/api/v1/catalog.tsv?platform=ps4").data.decode().strip().split("\t")
    assert line[1] == "Demo" and len(line[5]) == 64
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
