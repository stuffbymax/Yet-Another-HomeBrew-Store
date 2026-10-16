#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  ps3|ps4|ps5) exec "$(dirname "$0")/setup-$1.sh" "${@:2}" ;;
  *) echo "Usage: $0 {ps3|ps4|ps5}" >&2; exit 2 ;;
esac