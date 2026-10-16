#!/usr/bin/env bash
set -euo pipefail
export PLATFORM=ps5
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_command git
repository="${PS5_TOOLCHAIN_REPOSITORY:-}"
[[ -n "$repository" ]] || die "no maintained official open PS5 toolchain is currently configured; set PS5_TOOLCHAIN_REPOSITORY to an open Git repository you trust"
toolchain_root="${PS5_TOOLCHAIN_ROOT:-$PROJECT_ROOT/toolchains/ps5}"
clone_or_update "$repository" "$toolchain_root"
build_dir="$(prepare_build_dir "$PLATFORM" "$toolchain_root")"
echo "PS5 experimental open toolchain source is ready."
echo "  Source: $toolchain_root"
echo "  Build:  $build_dir"