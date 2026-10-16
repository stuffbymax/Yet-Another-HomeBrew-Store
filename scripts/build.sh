#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
platform="${1:-}"
build_dir="$PROJECT_ROOT/build/$platform"

case "$platform" in
  ps3|ps4|ps5) ;;
  *) printf 'Usage: %s {ps3|ps4|ps5} [cmake-build-options...]\n' "$0" >&2; exit 2 ;;
esac

[[ -f "$build_dir/toolchain.env" ]] ||
  { printf 'error: run scripts/setup-%s.sh first\n' "$platform" >&2; exit 1; }

command -v cmake >/dev/null 2>&1 || { echo "error: required command not found: cmake" >&2; exit 1; }
cmake --build "$build_dir" "$@"
