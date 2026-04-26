#!/usr/bin/env bash
# Start HDFS + cloud controller. Run on master as azureuser.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY_FILE="$REPO_DIR/.master_key"

# Load existing key, or create one on first run.
if [ -z "${MASTER_KEY_B64:-}" ]; then
  if [ -f "$KEY_FILE" ]; then
    export MASTER_KEY_B64="$(cat "$KEY_FILE")"
    echo "[key] loaded from $KEY_FILE"
  else
    export MASTER_KEY_B64="$(python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())')"
    umask 077
    echo "$MASTER_KEY_B64" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
    echo "[key] FIRST RUN: new AES-256 key generated and saved to $KEY_FILE"
    echo "      KEEP THIS FILE SAFE. Losing it = losing all uploaded files."
  fi
fi

echo "[1/2] start HDFS"
sudo -u hadoop /opt/hadoop/sbin/start-dfs.sh
sleep 3
sudo -u hadoop /opt/hadoop/bin/hdfs dfsadmin -safemode leave >/dev/null 2>&1 || true

echo "[2/2] start Flask controller (background, log -> controller.log)"
cd "$REPO_DIR/controller"
pkill -f "python app.py" || true
nohup env MASTER_KEY_B64="$MASTER_KEY_B64" \
          WEBHDFS_URL="${WEBHDFS_URL:-http://master:9870/webhdfs/v1}" \
          .venv/bin/python app.py > controller.log 2>&1 &
disown
sleep 2
echo "Flask PID: $(pgrep -f 'python app.py' || echo 'NOT RUNNING')"
echo
curl -sf http://localhost:5000/api/health && echo " <- Flask OK"
curl -sf http://localhost/api/health      && echo " <- nginx OK" || echo " (nginx not configured / not running)"
echo
PUBIP=$(curl -s ifconfig.me || echo '<master-public-ip>')
echo "Open: http://$PUBIP/"

