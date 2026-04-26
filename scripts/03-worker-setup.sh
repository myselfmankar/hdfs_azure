#!/usr/bin/env bash
# Run on EACH WORKER (worker-1, worker-2) after 01-common-setup.sh.
# Adds master's hadoop public key to this worker's authorized_keys.
set -euo pipefail

echo "Paste master's hadoop public key (from 02-master-setup.sh output),"
echo "then press ENTER then Ctrl-D:"
PUBKEY="$(cat)"

if [ -z "$PUBKEY" ]; then
  echo "No key provided. Aborting."
  exit 1
fi

sudo -u hadoop bash -c "
  mkdir -p ~/.ssh && chmod 700 ~/.ssh
  touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
  grep -qxF \"$PUBKEY\" ~/.ssh/authorized_keys || echo \"$PUBKEY\" >> ~/.ssh/authorized_keys
"
echo "Key installed for hadoop@$(hostname)."
