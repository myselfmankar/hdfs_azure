#!/usr/bin/env python3
"""
Cloud Mini — main orchestrator.
Run on master as azureuser.

Usage:
    python3 main.py start
    python3 main.py stop
    python3 main.py restart
    python3 main.py status
    python3 main.py logs
    python3 main.py setup       # first-time master setup
    python3 main.py worker      # first-time worker setup (run on each worker)
"""
import subprocess, sys, os, base64, stat, time

REPO_DIR  = os.path.dirname(os.path.abspath(__file__))
CTRL_DIR  = os.path.join(REPO_DIR, "controller")
KEY_FILE  = os.path.join(REPO_DIR, ".master_key")
LOG_FILE  = os.path.join(CTRL_DIR, "controller.log")
HADOOP    = "/opt/hadoop"

def run(cmd, check=True, capture=False):
    return subprocess.run(cmd, shell=True, check=check,
                          capture_output=capture, text=capture)

def _load_or_create_key():
    """Return MASTER_KEY_B64, generating + persisting on first call."""
    if os.path.isfile(KEY_FILE):
        key = open(KEY_FILE).read().strip()
        print(f"[key] loaded from {KEY_FILE}")
    else:
        key = base64.b64encode(os.urandom(32)).decode()
        # write with mode 600
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(KEY_FILE, flags, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(key + "\n")
        print(f"[key] FIRST RUN: new AES-256 key generated → {KEY_FILE}")
        print(      "      KEEP THIS FILE SAFE. Losing it = losing all uploaded data.")
    return key

# ─────────────────────────────────────────────────────────────────────────────
def _ensure_venv():
    venv_python = os.path.join(CTRL_DIR, ".venv", "bin", "python")
    if not os.path.isfile(venv_python):
        print("[venv] not found — creating now...")
        run(f"python3 -m venv {os.path.join(CTRL_DIR, '.venv')}")
        run(f"{os.path.join(CTRL_DIR, '.venv', 'bin', 'pip')} install --quiet --upgrade pip")
        run(f"{os.path.join(CTRL_DIR, '.venv', 'bin', 'pip')} install --quiet -r {os.path.join(CTRL_DIR, 'requirements.txt')}")
    return venv_python

def cmd_start():
    key = _load_or_create_key()

    print("\n[1/2] start HDFS")
    # check=False: start-dfs.sh exits non-zero if daemons are already running, which is fine
    run(f"sudo -u hadoop {HADOOP}/sbin/start-dfs.sh", check=False)
    time.sleep(3)
    run(f"sudo -u hadoop {HADOOP}/bin/hdfs dfsadmin -safemode leave", check=False)

    print("\n[2/2] start Flask controller")
    run("pkill -f 'python app.py' || true", check=False)
    env = os.environ.copy()
    env["MASTER_KEY_B64"] = key
    env["WEBHDFS_URL"]    = env.get("WEBHDFS_URL", "http://master:9870/webhdfs/v1")
    venv_python = _ensure_venv()
    log = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        [venv_python, "app.py"],
        cwd=CTRL_DIR, env=env,
        stdout=log, stderr=log,
        start_new_session=True
    )
    log.close()
    time.sleep(2)
    print(f"Flask PID: {proc.pid}")

    r = run("curl -sf http://localhost:5000/api/health", check=False, capture=True)
    print(f"Flask  → {'OK' if r.returncode == 0 else 'NOT RESPONDING'}")
    r = run("curl -sf http://localhost/api/health", check=False, capture=True)
    print(f"nginx  → {'OK' if r.returncode == 0 else 'not reachable'}")

    r = run("curl -s ifconfig.me", check=False, capture=True)
    pubip = r.stdout.strip() if r.returncode == 0 else "<master-public-ip>"
    print(f"\nOpen: http://{pubip}/")


def cmd_stop():
    print("[1/2] stop Flask controller")
    run("pkill -f 'python app.py' || true", check=False)
    run("pkill -f '.venv/bin/python app.py' || true", check=False)

    print("[2/2] stop HDFS")
    run(f"sudo -u hadoop {HADOOP}/sbin/stop-dfs.sh || true", check=False)

    print("Done.")
    run(f"sudo -u hadoop {HADOOP}/bin/hdfs dfsadmin -report 2>/dev/null || true", check=False)


def cmd_restart():
    cmd_stop()
    print()
    cmd_start()


def cmd_status():
    print("─── Hadoop processes (jps) ───")
    run(f"sudo -u hadoop {HADOOP}/bin/hdfs dfsadmin -report 2>/dev/null | head -10", check=False)
    print("\n─── Flask controller ───")
    run("pgrep -af 'python app.py' || echo '(not running)'", check=False)
    print("\n─── nginx ───")
    run("systemctl is-active nginx || echo '(not installed)'", check=False)
    print("\n─── HDFS live datanodes ───")
    run(f"sudo -u hadoop {HADOOP}/bin/hdfs dfsadmin -report 2>/dev/null "
        "| grep -E 'Live datanodes|Configured Capacity' || true", check=False)


def cmd_logs():
    if not os.path.isfile(LOG_FILE):
        print(f"Log file not found: {LOG_FILE}")
        sys.exit(1)
    run(f"tail -f {LOG_FILE}")


def cmd_setup():
    run(f"python3 {os.path.join(REPO_DIR, 'scripts', 'master-setup.py')}")


def cmd_worker():
    run(f"python3 {os.path.join(REPO_DIR, 'scripts', 'worker-setup.py')}")


# ─────────────────────────────────────────────────────────────────────────────
COMMANDS = {
    "start":   cmd_start,
    "stop":    cmd_stop,
    "restart": cmd_restart,
    "status":  cmd_status,
    "logs":    cmd_logs,
    "setup":   cmd_setup,
    "worker":  cmd_worker,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0)
    COMMANDS[sys.argv[1]]()
