#!/usr/bin/env bash
set -euo pipefail
export PLATFORM=ps3
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_command git
toolchain_root="${PS3_TOOLCHAIN_ROOT:-$PROJECT_ROOT/toolchains/ps3dev}"
clone_or_update "https://github.com/ps3dev/ps3dev.git" "$toolchain_root"
build_dir="$(prepare_build_dir "$PLATFORM" "$toolchain_root")"
echo "PS3 open toolchain source is ready."
echo "  Source: $toolchain_root"
echo "  Build:    $build_dir"
echo "Build it from the source directory with its documented build-all.sh workflow."
