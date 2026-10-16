#!/usr/bin/env bash
set -euo pipefail
export PLATFORM=ps4
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_command git
toolchain_root="${PS4_TOOLCHAIN_ROOT:-$PROJECT_ROOT/toolchains/openorbis-ps4}"
clone_or_update "https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain.git" "$toolchain_root"
build_dir="$(prepare_build_dir "$PLATFORM" "$toolchain_root")"
echo "PS4 alpha OpenOrbis toolchain source is ready."
echo "  Source: $toolchain_root"
echo "  Build:    $build_dir"
echo "Install clang/lld separately, then follow the toolchain repository's platform instructions."