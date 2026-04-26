#!/usr/bin/env bash
# Single entry point for cloud-mini.
# Usage:
#   ./run.sh setup     # full first-time install (master only). On workers run: ./run.sh worker
#   ./run.sh worker    # worker first-time install (run on each worker)
#   ./run.sh start     # start HDFS + Flask controller (master)
#   ./run.sh stop      # stop everything (master)
#   ./run.sh restart   # stop + start
#   ./run.sh status    # show what's running
#   ./run.sh logs      # tail controller log
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

chmod +x scripts/*.sh 2>/dev/null || true

cmd="${1:-help}"

case "$cmd" in
  setup)
    ./scripts/01-common-setup.sh
    ./scripts/02-master-setup.sh
    echo "Setup done. Run './run.sh start' to launch."
    ;;
  worker)
    ./scripts/01-common-setup.sh
    ./scripts/03-worker-setup.sh
    ;;
  start)
    ./scripts/start-all.sh
    ;;
  stop)
    ./scripts/stop-all.sh
    ;;
  restart)
    ./scripts/stop-all.sh || true
    ./scripts/start-all.sh
    ;;
  status)
    echo "--- Hadoop processes (jps) ---"
    sudo -u hadoop jps 2>/dev/null || echo "(hadoop user not set up)"
    echo
    echo "--- Flask controller ---"
    pgrep -af "python app.py" || echo "(not running)"
    echo
    echo "--- nginx ---"
    systemctl is-active nginx 2>/dev/null || echo "(not installed)"
    echo
    echo "--- HDFS report ---"
    sudo -u hadoop /opt/hadoop/bin/hdfs dfsadmin -report 2>/dev/null | head -10 || true
    ;;
  logs)
    tail -f controller/controller.log
    ;;
  help|*)
    cat <<USAGE
cloud-mini control script

Usage: ./run.sh <command>

  setup      Full first-time install on master (runs 01 + 02)
  worker     Worker first-time install (runs 01 + 03)
  start      Start HDFS + Flask controller
  stop       Stop everything
  restart    Stop + start
  status     Show running services
  logs       Tail controller.log
USAGE
    ;;
esac
