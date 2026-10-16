# Yet Another Homebrew Store

A shared Flask store for PS3, PS4, and PS5 homebrew packages. The platform is data-driven, so the same UI and database can serve all three targets while platform build tooling remains separate.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app init-db
flask --app app run
```

The application uses local SQLite storage at `instance/store.db`, stores uploads in
`instance/uploads`, limits packages to 512 MB, and generates a fresh secret key
when it starts. Keep uploads outside the repository and serve production traffic
through HTTPS with a reverse proxy. For a multi-process production deployment,
replace the in-process key and SQLite settings in `create_app()` with your
deployment's secret-management and database configuration.

## Security baseline

Passwords use Werkzeug's adaptive hashes; forms use CSRF protection; uploads are size-limited, extension allow-listed, renamed to random server-side names, and stored outside static files. Creator mutations require authentication and ownership. Every package gets a SHA-256 checksum.

This initial version deliberately does not execute or inspect uploaded binaries. A production deployment should add an isolated malware scanner, moderation/review workflow, object storage, malware scanning, rate limiting, email verification, and an external package-signing policy before public launch.

## Open toolchain scripts

The repository does not use, download, or require proprietary SDKs. The setup
scripts download source from public open-source repositories:

```bash
scripts/setup.sh ps3

scripts/setup.sh ps4
```

PS3 downloads [`ps3dev/ps3dev`](https://github.com/ps3dev/ps3dev), the complete
open PS3 development environment. PS4 downloads
[`OpenOrbis/OpenOrbis-PS4-Toolchain`](https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain),
the open PS4 toolchain. Both are cloned into ignored `toolchains/` directories
and can be overridden with `PS3_TOOLCHAIN_ROOT` or `PS4_TOOLCHAIN_ROOT`.

The PS4 script is explicitly an alpha entry point. It downloads source only;
follow each project's own dependency and build instructions to compile the
toolchain. The scripts do not execute arbitrary downloaded install scripts.

There is currently no maintained official open PS5 toolchain configured here.
The PS5 script requires an explicit repository to avoid presenting an unrelated
or untrusted project as a PS5 SDK:

```bash
PS5_TOOLCHAIN_REPOSITORY=https://example.org/your-open-ps5-toolchain.git \
scripts/setup.sh ps5
```

Review and trust that repository before running its build instructions.
`scripts/build.sh` is reserved for projects that provide a compatible CMake
build directory; PS3 and PS4 source builds follow their upstream instructions.

The scripts require Bash and CMake. They do not claim that a generic compiler
can target retail console hardware; platform-specific compatibility, compiler
flags, and packaging belong in the external toolchain supplied by the user.
