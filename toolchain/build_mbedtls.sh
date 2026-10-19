#!/usr/bin/env bash
# Cross-builds mbedTLS (static) for a console SDK. Usage:
#   CC=<cross cc> AR=<cross ar> ./build_mbedtls.sh <prefix> [extra CFLAGS...]
# e.g. PS5:  source ~/yahbs-sdk/env-ps5.sh; CC=prospero-clang AR=llvm-ar ./build_mbedtls.sh $HOME/yahbs-sdk/mbedtls-ps5
#      PS3:  source ~/yahbs-sdk/env-ps3.sh; CC=powerpc64-ps3-elf-gcc AR=powerpc64-ps3-elf-ar ./build_mbedtls.sh $HOME/yahbs-sdk/mbedtls-ps3
#      PC test: ./build_mbedtls.sh /tmp/mbedtls-host
source "$(dirname "$0")/_common.sh"
PREFIX="${1:?usage: build_mbedtls.sh <prefix> [cflags...]}"; shift || true
VER="${MBEDTLS_VER:-3.6.2}"
CC="${CC:-cc}"; AR="${AR:-ar}"
need curl; need make; need tar
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
log "Downloading mbedTLS $VER"
curl -fsSL "https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-$VER/mbedtls-$VER.tar.bz2" -o "$WORK/m.tar.bz2" \
  || die "download failed (network allow-list? try MBEDTLS_VER)"
tar -xjf "$WORK/m.tar.bz2" -C "$WORK"
cd "$WORK/mbedtls-$VER"
# Trim features a console client does not need; keep TLS1.2 + common curves/ciphers.
log "Building with CC=$CC"
make -C library -j"$(nproc 2>/dev/null || echo 2)" CC="$CC" AR="$AR" CFLAGS="-O2 $*" static
mkdir -p "$PREFIX/lib" "$PREFIX/include"
cp library/*.a "$PREFIX/lib/"; cp -r include/mbedtls include/psa "$PREFIX/include/"
log "Installed to $PREFIX  (use -I$PREFIX/include and -L$PREFIX/lib -lmbedtls -lmbedx509 -lmbedcrypto)"
