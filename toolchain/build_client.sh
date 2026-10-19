#!/usr/bin/env bash
# One command to build a YAHBS console client.   Usage:
#     ./build_client.sh ps4|ps5  https://your-store.example.com  [sdk_dir]
# It installs the SDK if missing, builds mbedTLS, and builds the client. Output lands in dist/.
# Before a real release: put YOUR public key in client/common/pubkey.h and YOUR CA in client/common/ca_pem.h.
source "$(dirname "$0")/_common.sh"
T="${1:?usage: $0 ps4|ps5 https://store.example.com [sdk_dir]}"; URL="${2:?store URL required}"
SDK="${3:-$HOME/yahbs-sdk}"; ROOT="$(cd "$(dirname "$0")/.." && pwd)"; mkdir -p "$ROOT/dist"
case "$URL" in https://*) ;; *) die "store URL must start with https://" ;; esac

# Refuse to build with the placeholder trust anchors that ship in the repo.
grep -q "0x12, 0xff, 0x86, 0xda" "$ROOT/client/common/pubkey.h" && \
  log "WARNING: client/common/pubkey.h is the TEST key; this build will reject your server's catalog."
grep -q "MIIDJTCCAg2gAwIBAgIULtgL8tifepnQTSqSUIGQ5xY0fpkw" "$ROOT/client/common/ca_pem.h" && \
  log "WARNING: client/common/ca_pem.h is the TEST certificate; HTTPS to your server will fail until you replace it."

case "$T" in
ps4)
  [ -x "$SDK/OpenOrbis/PS4Toolchain/bin/linux/create-fself" ] || bash "$(dirname "$0")/setup_ps4.sh" "$SDK"
  export OO_PS4_TOOLCHAIN="$SDK/OpenOrbis/PS4Toolchain" PATH="$PATH:$SDK/OpenOrbis/PS4Toolchain/bin/linux"
  [ -f "$SDK/mbedtls-ps4/lib/libmbedtls.a" ] || CC=clang AR=llvm-ar bash "$(dirname "$0")/build_mbedtls.sh" "$SDK/mbedtls-ps4" \
      --target=x86_64-pc-freebsd12-elf -fPIC -funwind-tables -ffunction-sections \
      -isysroot "$OO_PS4_TOOLCHAIN" -isystem "$OO_PS4_TOOLCHAIN/include" -DMBEDTLS_NO_PLATFORM_ENTROPY
  # PkgTool.Core is a .NET 3 app that needs OpenSSL 1.1; modern distros only ship 3.x, so fetch 1.1 locally.
  if ! ls /usr/lib/x86_64-linux-gnu/libssl.so.1.1 >/dev/null 2>&1; then
    if [ ! -f "$SDK/ssl11/usr/lib/x86_64-linux-gnu/libssl.so.1.1" ]; then
      mkdir -p "$SDK/ssl11"; ( cd "$SDK/ssl11" \
        && curl -fsSLO http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb \
        && dpkg -x libssl1.1_*.deb . ) || die "could not fetch libssl1.1 (needed by the PKG tool)"
    fi
    export LD_LIBRARY_PATH="$SDK/ssl11/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
  export DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
  make -C "$ROOT/client/ps4" clean >/dev/null
  make -C "$ROOT/client/ps4" MBEDTLS="$SDK/mbedtls-ps4" STORE_URL="$URL"
  cp "$ROOT"/client/ps4/*.pkg "$ROOT/dist/"
  make -C "$ROOT/client/ps4" clean >/dev/null
  ;;
ps5)
  [ -x "$SDK/ps5-payload-sdk/bin/prospero-clang" ] || bash "$(dirname "$0")/setup_ps5.sh" "$SDK"
  export PS5_PAYLOAD_SDK="$SDK/ps5-payload-sdk" PATH="$PATH:$SDK/ps5-payload-sdk/bin"
  [ -f "$SDK/mbedtls-ps5/lib/libmbedtls.a" ] || CC=prospero-clang AR=prospero-ar bash "$(dirname "$0")/build_mbedtls.sh" \
      "$SDK/mbedtls-ps5" -fPIC -ffunction-sections -DMBEDTLS_NO_PLATFORM_ENTROPY
  make -C "$ROOT/client/ps5" clean >/dev/null
  make -C "$ROOT/client/ps5" MBEDTLS="$SDK/mbedtls-ps5" STORE_URL="$URL"
  cp "$ROOT/client/ps5/yahbs-ps5.elf" "$ROOT/dist/"
  make -C "$ROOT/client/ps5" clean >/dev/null
  ;;
ps3) die "PS3 needs the PSL1GHT toolchain (setup_ps3.sh, ~1h GCC build) and is not verified yet: see README" ;;
*) die "unknown target $T" ;;
esac
log "Built. Output in $ROOT/dist/"; ls -l "$ROOT/dist"
