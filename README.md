# Yet Another HomeBrew Store (YAHBS)

One store, one database, three consoles. Creators upload homebrew on the website; console clients
(PS3 / PS4 / PS5, same UI, different SDK) read the same read-only API and download packages.

```
server/     Flask website + API + moderation (the one database)
client/     common/ portable C core (catalog, download, SHA-256)  host/ PC test build
            ps4/ alpha console client (OpenOrbis)
toolchain/  setup_ps3.sh  setup_ps4.sh  setup_ps5.sh  setup_all.sh
```

## Run the server (dev)
```bash
cd server && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
export YAHBS_ENV=development
flask --app app create-admin yourname you@example.com   # moderator account
flask --app app run
```
Production: set `SECRET_KEY`, `FORCE_HTTPS=1`, `PROXY_HOPS=1`, use PostgreSQL and Redis
(`RATELIMIT_STORAGE_URI`), run `gunicorn 'app:create_app()'` behind nginx with a real TLS certificate
(Let's Encrypt), and cap uploads in nginx too (`client_max_body_size`). Back up `instance/uploads` + DB.
`cd server && python -m pytest tests` runs the security tests.

## Security model
| Threat | Control |
|---|---|
| Password theft | scrypt hashes, 12-char minimum, constant-time-ish login, generic errors, 5 failures = 15 min lockout, per-IP rate limits |
| CSRF | Flask-WTF token on every POST (including logout, delete, approve) |
| XSS | Jinja autoescape, no inline JS/CSS, strict CSP (`default-src 'none'`), nosniff |
| Session theft | HttpOnly, Secure, SameSite=Lax cookies, 8 h lifetime, strong session protection, HSTS |
| SQL injection | SQLAlchemy ORM only, search uses escaped `contains` |
| IDOR | Every edit/delete checks owner or admin; others get 404; unapproved apps are invisible |
| Malicious uploads | extension allow-list + magic-byte check per platform, random server-side filenames, stored outside web root, served as attachment, size cap, icons re-encoded by Pillow |
| Malware in store | every new app and every new package goes to moderator review before it is public |
| Tampered downloads | SHA-256 computed server-side, shown on the site, and **verified by the client before the file is kept** |
| Open redirect / clickjacking | `next` validated, `X-Frame-Options: DENY` |

Not covered yet (do before public launch): email verification + password reset, 2FA for admins,
signed catalog (Ed25519) so a compromised/misconfigured TLS path cannot swap hashes, malware scanning,
DB migrations (Alembic), abuse-report button, audit log page.

## API (read-only, approved apps only)
`GET /api/v1/apps?platform=ps4` JSON · `GET /api/v1/apps/<id>` · `GET /api/v1/catalog.tsv?platform=ps4`
(tab-separated `id name version platform size sha256`, used by the C client) · `GET /app/<id>/download`

## Toolchains
```bash
cd toolchain
./setup_ps4.sh        # OpenOrbis (alpha target)
./setup_ps3.sh        # ps3dev/ps3toolchain + PSL1GHT (slow: builds GCC)
./setup_ps5.sh        # ps5-payload-sdk
source ~/yahbs-sdk/env-ps4.sh
```
The scripts install only open-source SDKs. They contain no exploits and do not enable homebrew on a
console; you need a console already running a homebrew-capable environment.

## Client status
- `client/common`: tested on PC (`cd client/host && make && ./yahbs_host http://127.0.0.1:5000 ps4 1`),
  including a tampered-package test.
- `client/ps4`: **alpha, untested on hardware, not compiled here**: the OpenOrbis headers/flags were written
  from memory of the upstream samples, so expect small fixes on first build. Currently logs the catalog and
  downloads the first app to the debug log; no on-screen UI yet.
- PS3 / PS5: only `plat_http_get()` has to be implemented (`platform_ps3.c`, `platform_ps5.c`), the core is shared.

## Roadmap
1. Fix-ups from first real PS4 build; TLS certificate validation (blocker for beta).
2. Shared UI layer (grid of icons, detail page, progress bar) drawn once in `common/`, backends per SDK.
3. Install step (PS4: place pkg for the on-console installer; PS5: run ELF payload; PS3: .pkg install).
4. Signed catalog, email verification, 2FA, malware scanning.
