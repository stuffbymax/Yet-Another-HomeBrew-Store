# Shared helpers, sourced by the setup scripts.
set -euo pipefail
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
log()  { printf '\033[1;34m[yahbs]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[yahbs] %s\033[0m\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"; }
apt_install() {
  if command -v apt-get >/dev/null 2>&1; then
    log "Installing packages via apt (sudo)…"
    $SUDO apt-get update -y && $SUDO apt-get install -y "$@"
  else
    log "Not a Debian/Ubuntu system. Install these yourself: $*"
  fi
}
# Pin a git checkout to a ref (tag/commit) if YAHBS_<NAME>_REF is set; otherwise track default branch.
clone() { # url dir [ref]
  if [ -d "$2/.git" ]; then git -C "$2" pull --ff-only; else git clone --depth 1 ${3:+--branch "$3"} "$1" "$2"; fi
}
