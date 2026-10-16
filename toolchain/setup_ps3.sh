#!/usr/bin/env bash
# PS3 toolchain setup (ps3dev/ps3toolchain + PSL1GHT). Builds GCC for PPU/SPU: takes 30-90 min.
# Usage: ./setup_ps3.sh [install_dir]
source "$(dirname "$0")/_common.sh"
DIR="${1:-$HOME/yahbs-sdk}"; mkdir -p "$DIR"
export PS3DEV="$DIR/ps3dev"
export PSL1GHT="$PS3DEV"
export PATH="$PATH:$PS3DEV/bin:$PS3DEV/ppu/bin:$PS3DEV/spu/bin"

apt_install autoconf automake bison flex gcc g++ libelf-dev make texinfo libncurses-dev \
  patch python3 python-is-python3 wget zlib1g-dev libtool libtool-bin bzip2 libgmp3-dev \
  pkg-config libssl-dev git xz-utils
need git; need make; need gcc

mkdir -p "$PS3DEV"
clone https://github.com/ps3dev/ps3toolchain.git "$DIR/ps3toolchain" "${YAHBS_PS3TC_REF:-}"
log "Building toolchain (this is slow)…"
( cd "$DIR/ps3toolchain" && ./toolchain.sh )

cat > "$DIR/env-ps3.sh" <<ENV
export PS3DEV="$PS3DEV"
export PSL1GHT="$PS3DEV"
export PATH="\$PATH:$PS3DEV/bin:$PS3DEV/ppu/bin:$PS3DEV/spu/bin"
ENV
need powerpc64-ps3-elf-gcc || true
log "Done. Activate with:  source $DIR/env-ps3.sh"
