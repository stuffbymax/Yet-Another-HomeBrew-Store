#!/usr/bin/env bash
# PS4 toolchain setup (OpenOrbis, official release build). Linux / WSL2.  Usage: ./setup_ps4.sh [install_dir]
# NOTE: the git repo alone has no compiled tools/libraries, so this downloads the release tarball.
source "$(dirname "$0")/_common.sh"
DIR="${1:-$HOME/yahbs-sdk}"; mkdir -p "$DIR"

apt_install git make clang lld llvm curl unzip libicu-dev libssl-dev xz-utils
need curl; need clang; need ld.lld

REPO="https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain"
TAG="${YAHBS_OO_TAG:-$(curl -sI "$REPO/releases/latest" | tr -d '\r' | awk -F/ 'tolower($1) ~ /^location/ {print $NF}')}"
[ -n "$TAG" ] || die "could not determine the latest OpenOrbis release (set YAHBS_OO_TAG=v0.5.4)"
ASSET="$(curl -s "$REPO/releases/expanded_assets/$TAG" | grep -o "releases/download/$TAG/toolchain-llvm-[0-9]*\.tar\.gz" | sort -V | tail -1)"
[ -n "$ASSET" ] || die "no toolchain tarball found for $TAG"

if [ ! -x "$DIR/OpenOrbis/PS4Toolchain/bin/linux/create-fself" ]; then
  log "Downloading OpenOrbis $TAG ($ASSET) ~160 MB…"
  curl -fL "$REPO/$ASSET" -o "$DIR/oo.tar.gz" || die "download failed (network allow-list?)"
  tar -xzf "$DIR/oo.tar.gz" -C "$DIR" && rm -f "$DIR/oo.tar.gz"
fi
OO="$DIR/OpenOrbis/PS4Toolchain"
for p in include lib/crt1.o link.x bin/linux/create-fself bin/linux/create-gp4 bin/linux/PkgTool.Core; do
  [ -e "$OO/$p" ] || die "toolchain layout changed: $OO/$p missing"
done
chmod +x "$OO"/bin/linux/* 2>/dev/null || true

cat > "$DIR/env-ps4.sh" <<ENV
export OO_PS4_TOOLCHAIN="$OO"
export PATH="\$PATH:$OO/bin/linux"
ENV
log "Done. Activate with:  source $DIR/env-ps4.sh"
