#!/usr/bin/env bash
# Usage: ./setup_all.sh [ps3] [ps4] [ps5]   (default: ps4 only, since PS4 is the alpha target)
here="$(dirname "$0")"
targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(ps4)
for t in "${targets[@]}"; do
  case "$t" in ps3|ps4|ps5) bash "$here/setup_$t.sh" ;; *) echo "unknown target $t"; exit 1 ;; esac
done
