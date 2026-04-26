#!/usr/bin/env bash
# Bootstrap script — run ONCE on a fresh VM as azureuser.
# Installs git + python3, clones the repo, then hands off to Python.
#
# Master:   curl -fsSL https://raw.githubusercontent.com/myselfmankar/hdfs_azure/main/setup.sh | bash
# Worker:   same command, then choose 'worker' when prompted
set -euo pipefail

REPO_URL="https://github.com/myselfmankar/hdfs_azure.git"
REPO_DIR="$HOME/hdfs_azure"

echo "[bootstrap] apt update + git + python3"
sudo apt-get update -y -q
sudo apt-get install -y -q git python3 python3-pip python3-venv

echo "[bootstrap] clone / update repo"
if [ -d "$REPO_DIR/.git" ]; then
  cd "$REPO_DIR" && git pull
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"

echo
echo "What is this VM?"
echo "  1) master"
echo "  2) worker"
read -rp "Choice [1/2]: " choice

case "$choice" in
  1) python3 main.py setup  ;;
  2) python3 main.py worker ;;
  *) echo "Invalid choice. Run 'python3 main.py setup' or 'python3 main.py worker' manually." ;;
esac
