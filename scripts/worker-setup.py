#!/usr/bin/env python3
"""
Worker-node first-time setup.
Run on EACH worker VM (worker-1, worker-2) as azureuser:
    python3 scripts/worker-setup.py
"""
import subprocess, sys, os, textwrap

HADOOP_VERSION = "3.3.6"
MASTER_IP  = "10.0.0.4"
WORKER1_IP = "10.0.0.5"
WORKER2_IP = "10.0.0.6"

def run(cmd, check=True):
    print(f"  $ {cmd}")
    subprocess.run(cmd, shell=True, check=check)

def write_sudo(path, content):
    subprocess.run(["sudo", "tee", path],
                   input=content.encode(), stdout=subprocess.DEVNULL, check=True)

# ── Step 1: packages ──────────────────────────────────────────────────────────
print("\n[1/6] apt update + base packages")
run("sudo apt-get update -y")
run("sudo apt-get install -y openjdk-11-jdk wget python3-pip python3-venv ssh rsync")

# ── Step 2: /etc/hosts ────────────────────────────────────────────────────────
print("\n[2/6] /etc/hosts")
run("sudo sed -i '/# hadoop-cluster/,/# hadoop-cluster-end/d' /etc/hosts")
hosts_block = textwrap.dedent(f"""\
    # hadoop-cluster
    {MASTER_IP}  master
    {WORKER1_IP} worker1
    {WORKER2_IP} worker2
    # hadoop-cluster-end
""")
subprocess.run("sudo tee -a /etc/hosts", shell=True,
               input=hosts_block.encode(), stdout=subprocess.DEVNULL, check=True)

# ── Step 3: hadoop user ───────────────────────────────────────────────────────
print("\n[3/6] hadoop user")
run('id hadoop >/dev/null 2>&1 || sudo adduser --disabled-password --gecos "" hadoop')
run("sudo usermod -aG sudo hadoop")
write_sudo("/etc/sudoers.d/hadoop", "hadoop ALL=(ALL) NOPASSWD:ALL\n")

# ── Step 4: Hadoop tarball ────────────────────────────────────────────────────
print(f"\n[4/6] Hadoop {HADOOP_VERSION}")
if not os.path.isdir("/opt/hadoop"):
    tgz = f"hadoop-{HADOOP_VERSION}.tar.gz"
    url = f"https://downloads.apache.org/hadoop/common/hadoop-{HADOOP_VERSION}/{tgz}"
    run(f"cd /tmp && ([ -f {tgz} ] || wget -q {url})")
    run(f"sudo tar -xzf /tmp/hadoop-{HADOOP_VERSION}.tar.gz -C /opt")
    run(f"sudo mv /opt/hadoop-{HADOOP_VERSION} /opt/hadoop")
run("sudo chown -R hadoop:hadoop /opt/hadoop")
run("sudo -u hadoop mkdir -p /opt/hadoop/data/data /opt/hadoop/logs")

# ── Step 5: env vars ──────────────────────────────────────────────────────────
print("\n[5/6] /etc/profile.d/hadoop.sh")
write_sudo("/etc/profile.d/hadoop.sh", textwrap.dedent("""\
    export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
    export HADOOP_HOME=/opt/hadoop
    export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
    export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
"""))
run("sudo chmod +x /etc/profile.d/hadoop.sh")

# ── Step 6: JAVA_HOME in hadoop-env.sh ───────────────────────────────────────
print("\n[6/6] hadoop-env.sh JAVA_HOME")
env_file = "/opt/hadoop/etc/hadoop/hadoop-env.sh"
run(f"""sudo -u hadoop bash -c '
  grep -q "^export JAVA_HOME=" {env_file} \
    && sudo sed -i "s|^export JAVA_HOME=.*|export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64|" {env_file} \
    || echo "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64" >> {env_file}
'""")

# ── Step 7: install master's public key ──────────────────────────────────────
print("\n[7/7] Paste master's hadoop public key.")
print("(Copy it from master-setup.py output, then press ENTER, then Ctrl-D)\n")
lines = []
try:
    while True:
        line = input()
        lines.append(line)
except EOFError:
    pass
pubkey = "\n".join(lines).strip()

if not pubkey:
    print("ERROR: no key provided. Re-run and paste the key.")
    sys.exit(1)

subprocess.run(["sudo", "-u", "hadoop", "bash", "-c",
    f"""mkdir -p ~/.ssh && chmod 700 ~/.ssh
    touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
    grep -qxF '{pubkey}' ~/.ssh/authorized_keys || echo '{pubkey}' >> ~/.ssh/authorized_keys"""
], check=True)

import socket
print(f"\n✓ Worker setup complete on {socket.gethostname()}.")
print("  Go back to master and press ENTER to continue master-setup.py.")
