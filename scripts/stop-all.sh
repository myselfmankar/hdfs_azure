#!/usr/bin/env bash
# Stop everything: cloud controller (Flask) + HDFS.
# Run on master as azureuser.
set -euo pipefail

echo "[1/2] stop Flask controller (if running via nohup)"
pkill -f "python app.py" || true
pkill -f ".venv/bin/python app.py" || true

echo "[2/2] stop HDFS"
sudo -u hadoop /opt/hadoop/sbin/stop-dfs.sh || true

echo "Done. 'jps' should show no Hadoop processes:"
sudo -u hadoop jps || true
