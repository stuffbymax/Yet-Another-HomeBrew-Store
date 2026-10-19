# Yet Another HomeBrew Store (YAHBS)

One store, one database, three consoles. Creators upload homebrew on the website; console clients
(PS3 / PS4 / PS5, same UI, different SDK) read the same read-only API and download packages.

```
server/     Flask website + API + moderation (the one database)
client/     common/ portable C core (catalog, download, SHA-256)  host/ PC test build
            ps4/ alpha console client (OpenOrbis)
toolchain/  setup_ps3.sh  setup_ps4.sh  setup_ps5.sh  setup_all.sh
```

## Quick start (3 commands)
```bash
./make-key.sh                       # makes the signing key + puts both halves where they belong (see below)
cd server && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
flask --app app db upgrade && flask --app app create-admin yourname you@example.com && gunicorn 'app:create_app()'
```
**What `make-key.sh` does:** creates the signing key pair, writes the *secret* to `server/.env`
(the server reads that file by itself; it also fills in `SECRET_KEY`) and the *public* half to
`client/common/pubkey.h` (built into the console app). Run it once. It refuses to run again so you can't
break installed apps by accident; `./make-key.sh --force` replaces the key, after which you must rebuild the
console app. Never share or commit `server/.env`.

For local development use `export YAHBS_ENV=development` and `flask --app app run` instead of gunicorn.
Production: put it behind nginx with a Let's Encrypt certificate, set `FORCE_HTTPS=1` and `PROXY_HOPS=1`,
prefer PostgreSQL and Redis (`RATELIMIT_STORAGE_URI`), cap uploads in nginx (`client_max_body_size`), and
back up `instance/uploads` + the database. `cd server && python -m pytest tests` runs the security tests.

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

## Using a prebuilt PS4 package
The store address is not baked in: the app reads it from `/data/yahbs/config.txt` on the console (one line,
e.g. `https://store.example.com`). The package trusts the Let's Encrypt root certificates and one signing key
(`client/common/pubkey.h`); the matching secret goes in the server's `SIGNING_KEY_HEX`.

## Build the PS4 app (the lazy way)
```bash
./make-key.sh                                            # once (skip if you already ran it)
toolchain/build_client.sh ps4 https://store.example.com  # -> dist/*.pkg   (downloads the SDK the first time)
```
The app trusts Let's Encrypt certificates out of the box. For another CA:
`toolchain/make_ca_header.sh your-ca.pem > client/common/ca_pem.h` before building.
(PS5 works the same way with `ps5` and produces `dist/yahbs-ps5.elf`.)
Needs a Linux box or WSL2 with internet and about 1 GB free. The script warns if you are still using the
test key / test certificate that ship in the repo (builds made with them will not talk to your server).
Release builds accept HTTPS only; `-DYAHBS_ALLOW_HTTP` is for local testing.

## Client status (what is actually verified)
All consoles share one core: signed catalog, TLS, hash-verified download, and a software-rendered UI
(list, detail page with SHA-256, progress bar). Console backends only provide framebuffer, pad,
entropy, clock and a download folder (`plat_*` functions).

| Piece | Status |
|---|---|
| Catalog signature (Ed25519), replay/platform/tamper checks | **Tested**: 13 C tests pass on x86-64 and on big-endian PowerPC (qemu-ppc64, the PS3's architecture) |
| TLS + signed catalog + hash-checked download | **Tested** on PC against the live Flask server (good file OK, tampered file rejected, partial file deleted) |
| Shared UI | **Tested** on PC: renders real frames from the live server, including a mid-download progress bar (`client/host/ui_host`) |
| PS4 client | **Builds with the real OpenOrbis toolchain** (v0.5.4, LLVM 18) into a valid `.pkg`. **Never run on a console.** |
| PS5 client | **Builds with the real ps5-payload-sdk.** Headless (reads `/data/yahbs/queue.txt`). Logic tested on PC; **never run on a console.** |
| PS3 client | Written but **not built**: the GCC sources for the PS3 toolchain could not be downloaded here. Unverified. TLS stays off until `YAHBS_PS3_RANDOM_SYSCALL` is set (hardware RNG syscall number), on purpose |
| PS5 on-screen UI | **Not implemented**: display/pad functions return "unavailable" (could not verify the API for a payload) |
| Install step | Stages the verified file and tells the user how to install it; nothing auto-executes |

## Roadmap
1. First run on real hardware (PS4, PS5) and a first real PS3 build.
2. PS5 display/pad (or a local web UI) once the target environment is chosen.
3. Fully automatic install where the platform allows it.
4. Server: DB migrations are in `server/migrations`; add Redis rate limiting and PostgreSQL for production.
