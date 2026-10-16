#!/usr/bin/env bash
# PS5 payload SDK setup (ps5-payload-dev/sdk).  Usage: ./setup_ps5.sh [install_dir]
# Output programs are ELF payloads that run on consoles ALREADY running a homebrew-enabled
# environment. This script contains no exploit and does not enable homebrew on a console.
source "$(dirname "$0")/_common.sh"
DIR="${1:-$HOME/yahbs-sdk}"; mkdir -p "$DIR"
export PS5_PAYLOAD_SDK="$DIR/ps5-payload-sdk"

apt_install git make clang lld llvm cmake bash curl xxd
need git; need clang; need ld.lld; need make

clone https://github.com/ps5-payload-dev/sdk.git "$DIR/ps5-payload-sdk-src" "${YAHBS_PS5SDK_REF:-}"
log "Building and installing SDK to $PS5_PAYLOAD_SDK …"
( cd "$DIR/ps5-payload-sdk-src" && make clean && make && make DESTDIR="$PS5_PAYLOAD_SDK" install )

cat > "$DIR/env-ps5.sh" <<ENV
export PS5_PAYLOAD_SDK="$PS5_PAYLOAD_SDK"
export PATH="\$PATH:$PS5_PAYLOAD_SDK/bin"
ENV
log "Done. Activate with:  source $DIR/env-ps5.sh"
