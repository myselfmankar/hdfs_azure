#!/usr/bin/env bash
# Start HDFS + cloud controller. Run on master as azureuser.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${MASTER_KEY_B64:-}" ]; then
  echo "ERROR: export MASTER_KEY_B64=... before running (your AES key)."
  echo "Generate a fresh one with:"
  echo '  python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"'
  exit 1
fi

echo "[1/2] start HDFS"
sudo -u hadoop /opt/hadoop/sbin/start-dfs.sh
sleep 3
sudo -u hadoop /opt/hadoop/bin/hdfs dfsadmin -report | head -20 || true

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
curl -s http://localhost:5000/api/health && echo " <- Flask OK"
curl -s http://localhost/api/health      && echo " <- nginx OK"
echo
echo "Open: http://<master-public-ip>/"
