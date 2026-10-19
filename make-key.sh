#!/usr/bin/env bash
# Generates the catalog signing key and puts each half where it belongs:
#   secret  -> server/.env            (SIGNING_KEY_HEX=...)   never share this
#   public  -> client/common/pubkey.h (built into the console app)
# Usage:  ./make-key.sh            (first time)
#         ./make-key.sh --force    (replace an existing key: old console builds stop working, rebuild them)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
ENV="$here/server/.env"; PUB="$here/client/common/pubkey.h"
command -v openssl >/dev/null || { echo "openssl is required (sudo apt install openssl)"; exit 1; }

if [ -f "$ENV" ] && grep -Eq '^SIGNING_KEY_HEX=[0-9a-fA-F]{64}$' "$ENV" && [ "${1:-}" != "--force" ]; then
  echo "A signing key already exists in server/.env."
  echo "Replacing it makes every console app you already built reject your server."
  echo "If you really want a new one:  ./make-key.sh --force"
  exit 1
fi

umask 077
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
openssl genpkey -algorithm ed25519 -outform DER -out "$tmp"
hex() { od -An -tx1 -v | tr -d ' \n'; }
SEED="$(tail -c 32 "$tmp" | hex)"
PUBHEX="$(openssl pkey -inform DER -in "$tmp" -pubout -outform DER | tail -c 32 | hex)"
[ ${#SEED} -eq 64 ] && [ ${#PUBHEX} -eq 64 ] || { echo "key generation failed"; exit 1; }

# server/.env: create from the example if missing, then set the key line
[ -f "$ENV" ] || { cp "$here/server/.env.example" "$ENV" 2>/dev/null || : > "$ENV"; }
if grep -q '^SIGNING_KEY_HEX=' "$ENV"; then sed -i "s/^SIGNING_KEY_HEX=.*/SIGNING_KEY_HEX=$SEED/" "$ENV"
else printf '\nSIGNING_KEY_HEX=%s\n' "$SEED" >> "$ENV"; fi
# the server refuses to start in production without a SECRET_KEY: fill it in if it is empty
if ! grep -Eq '^SECRET_KEY=.+' "$ENV"; then
  SK="$(openssl rand -hex 32)"
  if grep -q '^SECRET_KEY=' "$ENV"; then sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SK/" "$ENV"; else printf 'SECRET_KEY=%s\n' "$SK" >> "$ENV"; fi
fi
chmod 600 "$ENV"

# client/common/pubkey.h
printf '#define YAHBS_PUBKEY { %s }\n' "$(echo "$PUBHEX" | sed 's/../0x&, /g; s/, $//')" > "$PUB"

echo "Done."
echo "  secret key -> server/.env   (keep private, never commit it; the server reads this file itself)"
echo "  public key -> client/common/pubkey.h"
echo
echo "Next:  1) restart the server   2) rebuild the console app:  toolchain/build_client.sh ps4 https://your-store"
