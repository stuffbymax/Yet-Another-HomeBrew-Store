#!/usr/bin/env bash
# PS4 toolchain setup (OpenOrbis). Linux / WSL2.  Usage: ./setup_ps4.sh [install_dir]
source "$(dirname "$0")/_common.sh"
DIR="${1:-$HOME/yahbs-sdk}"; mkdir -p "$DIR"

apt_install git make clang lld llvm curl unzip libicu-dev libssl-dev
need git; need clang; need ld.lld

log "Fetching OpenOrbis PS4 toolchain…"
clone https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain.git "$DIR/OpenOrbis-PS4-Toolchain" "${YAHBS_OO_REF:-}"
OO="$DIR/OpenOrbis-PS4-Toolchain"

# Sanity-check the layout we rely on; upstream may move things, so fail loudly.
for p in include lib bin/linux; do [ -e "$OO/$p" ] || die "unexpected toolchain layout: $OO/$p not found (check upstream README)"; done
chmod +x "$OO"/bin/linux/* 2>/dev/null || true

cat > "$DIR/env-ps4.sh" <<ENV
export OO_PS4_TOOLCHAIN="$OO"
export PATH="\$PATH:$OO/bin/linux"
ENV
log "Done. Activate with:  source $DIR/env-ps4.sh"
log "Then build the YAHBS alpha client:  cd client/ps4 && make && make pkg"
