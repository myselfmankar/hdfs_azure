#!/usr/bin/env python3
"""
Master-node first-time setup.
Run on the master VM as azureuser:
    python3 scripts/master-setup.py
"""
import subprocess, sys, os, textwrap

HADOOP_VERSION = "3.3.6"
MASTER_IP  = "10.0.0.4"
WORKER1_IP = "10.0.0.5"
WORKER2_IP = "10.0.0.6"
HCONF      = "/opt/hadoop/etc/hadoop"

def run(cmd, check=True):
    print(f"  $ {cmd}")
    subprocess.run(cmd, shell=True, check=check)

def write_sudo(path, content):
    """Write a file that needs root, via sudo tee."""
    subprocess.run(["sudo", "tee", path],
                   input=content.encode(), stdout=subprocess.DEVNULL, check=True)

def write_hadoop(path, content):
    """Write a file owned by the hadoop user."""
    subprocess.run(["sudo", "-u", "hadoop", "tee", path],
                   input=content.encode(), stdout=subprocess.DEVNULL, check=True)

# ── Step 1: packages ──────────────────────────────────────────────────────────
print("\n[1/9] apt update + base packages")
run("sudo apt-get update -y")
run("sudo apt-get install -y openjdk-11-jdk wget python3-pip python3-venv ssh rsync nginx")

# ── Step 2: /etc/hosts ────────────────────────────────────────────────────────
print("\n[2/9] /etc/hosts")
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
print("\n[3/9] hadoop user")
run('id hadoop >/dev/null 2>&1 || sudo adduser --disabled-password --gecos "" hadoop')
run("sudo usermod -aG sudo hadoop")
write_sudo("/etc/sudoers.d/hadoop", "hadoop ALL=(ALL) NOPASSWD:ALL\n")

# ── Step 4: Hadoop tarball ────────────────────────────────────────────────────
print(f"\n[4/9] Hadoop {HADOOP_VERSION}")
if not os.path.isdir("/opt/hadoop"):
    tgz = f"hadoop-{HADOOP_VERSION}.tar.gz"
    url = f"https://downloads.apache.org/hadoop/common/hadoop-{HADOOP_VERSION}/{tgz}"
    run(f"cd /tmp && ([ -f {tgz} ] || wget -q {url})")
    run(f"sudo tar -xzf /tmp/hadoop-{HADOOP_VERSION}.tar.gz -C /opt")
    run(f"sudo mv /opt/hadoop-{HADOOP_VERSION} /opt/hadoop")
run("sudo chown -R hadoop:hadoop /opt/hadoop")

# ── Step 5: env vars ──────────────────────────────────────────────────────────
print("\n[5/9] /etc/profile.d/hadoop.sh")
write_sudo("/etc/profile.d/hadoop.sh", textwrap.dedent("""\
    export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
    export HADOOP_HOME=/opt/hadoop
    export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
    export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
"""))
run("sudo chmod +x /etc/profile.d/hadoop.sh")

# ── Step 6: JAVA_HOME in hadoop-env.sh ───────────────────────────────────────
print("\n[6/9] hadoop-env.sh JAVA_HOME")
env_file = f"{HCONF}/hadoop-env.sh"
run(f"""sudo -u hadoop bash -c '
  grep -q "^export JAVA_HOME=" {env_file} \
    && sudo sed -i "s|^export JAVA_HOME=.*|export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64|" {env_file} \
    || echo "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64" >> {env_file}
'""")

# ── Step 7: hadoop SSH key + worker trust ────────────────────────────────────
print("\n[7/9] hadoop user SSH keypair")
run("""sudo -u hadoop bash -c '
  mkdir -p ~/.ssh && chmod 700 ~/.ssh
  [ -f ~/.ssh/id_rsa ] || ssh-keygen -t rsa -P "" -f ~/.ssh/id_rsa
  grep -qxF "$(cat ~/.ssh/id_rsa.pub)" ~/.ssh/authorized_keys 2>/dev/null \
    || cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
  chmod 600 ~/.ssh/authorized_keys
  ssh-keyscan -H master worker1 worker2 >> ~/.ssh/known_hosts 2>/dev/null || true
'""")

print("\n>>> COPY THIS PUBLIC KEY to each worker <<<")
subprocess.run("sudo -u hadoop cat /home/hadoop/.ssh/id_rsa.pub", shell=True)
print("\n>>> Then run on each worker:  python3 scripts/worker-setup.py <<<\n")
input("Press ENTER once you have run worker-setup.py on BOTH workers... ")

# ── Step 8: Hadoop XML configs ────────────────────────────────────────────────
print("\n[8/9] Hadoop XML configs + push to workers")
write_hadoop(f"{HCONF}/core-site.xml", textwrap.dedent("""\
    <?xml version="1.0"?>
    <configuration>
      <property><name>fs.defaultFS</name><value>hdfs://master:9000</value></property>
      <property><name>hadoop.http.staticuser.user</name><value>hadoop</value></property>
    </configuration>
"""))

write_hadoop(f"{HCONF}/hdfs-site.xml", textwrap.dedent("""\
    <?xml version="1.0"?>
    <configuration>
      <property><name>dfs.replication</name><value>2</value></property>
      <property><name>dfs.namenode.name.dir</name><value>/opt/hadoop/data/name</value></property>
      <property><name>dfs.datanode.data.dir</name><value>/opt/hadoop/data/data</value></property>
      <property><name>dfs.webhdfs.enabled</name><value>true</value></property>
      <property><name>dfs.namenode.http-address</name><value>0.0.0.0:9870</value></property>
      <property><name>dfs.namenode.rpc-bind-host</name><value>0.0.0.0</value></property>
    </configuration>
"""))

write_hadoop(f"{HCONF}/workers", "worker1\nworker2\n")

run("sudo -u hadoop mkdir -p /opt/hadoop/data/name /opt/hadoop/data/data /opt/hadoop/logs")

for host in ["worker1", "worker2"]:
    run(f"sudo -u hadoop scp -o StrictHostKeyChecking=no "
        f"{HCONF}/core-site.xml {HCONF}/hdfs-site.xml {HCONF}/workers {HCONF}/hadoop-env.sh "
        f"hadoop@{host}:{HCONF}/")

# ── Step 9: Format NameNode + start HDFS ──────────────────────────────────────
print("\n[9/9] Format NameNode + start HDFS")
run("sudo -u hadoop /opt/hadoop/sbin/stop-dfs.sh", check=False)

if not os.path.isfile("/opt/hadoop/data/name/current/VERSION"):
    # wipe worker datanodes first to avoid clusterID mismatch
    for host in ["worker1", "worker2"]:
        run(f"sudo -u hadoop ssh hadoop@{host} "
            f"'rm -rf /opt/hadoop/data/data && mkdir -p /opt/hadoop/data/data'", check=False)
    run("sudo -u hadoop /opt/hadoop/bin/hdfs namenode -format -nonInteractive -force")

run("sudo -u hadoop /opt/hadoop/sbin/start-dfs.sh")
import time; time.sleep(5)
run("sudo -u hadoop /opt/hadoop/bin/hdfs dfsadmin -safemode leave", check=False)
run("sudo -u hadoop /opt/hadoop/bin/hdfs dfs -mkdir -p /cloud/blocks")
run("sudo -u hadoop /opt/hadoop/bin/hdfs dfs -chmod 777 /cloud/blocks")

# ── Python venv ───────────────────────────────────────────────────────────────
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ctrl = os.path.join(repo, "controller")
run(f"python3 -m venv {ctrl}/.venv")
run(f"{ctrl}/.venv/bin/pip install --quiet --upgrade pip")
run(f"{ctrl}/.venv/bin/pip install --quiet -r {ctrl}/requirements.txt")

# ── nginx ─────────────────────────────────────────────────────────────────────
nginx_conf = textwrap.dedent("""\
    server {
        listen 80 default_server;
        server_name _;
        client_max_body_size 1024m;
        proxy_read_timeout 600;
        proxy_send_timeout 600;
        location / {
            proxy_pass http://127.0.0.1:5000;
            proxy_set_header Host             $host;
            proxy_set_header X-Real-IP        $remote_addr;
            proxy_set_header X-Forwarded-For  $proxy_add_x_forwarded_for;
            proxy_buffering         off;
            proxy_request_buffering off;
            proxy_http_version      1.1;
            proxy_set_header        Connection "";
        }
    }
""")
write_sudo("/etc/nginx/sites-available/cloud-controller", nginx_conf)
run("sudo ln -sf /etc/nginx/sites-available/cloud-controller /etc/nginx/sites-enabled/cloud-controller")
run("sudo rm -f /etc/nginx/sites-enabled/default")
run("sudo nginx -t && sudo systemctl restart nginx && sudo systemctl enable nginx")

print("\n✓ Master setup complete. Run:  python3 main.py start")
