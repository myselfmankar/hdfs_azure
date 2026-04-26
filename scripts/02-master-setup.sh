#!/usr/bin/env bash
# Run on MASTER only, AFTER 01-common-setup.sh has been run on all 3 VMs.
# Generates SSH key for the hadoop user, writes Hadoop configs,
# distributes them, formats NameNode, starts HDFS, and launches the controller.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/7] hadoop user SSH key"
sudo -u hadoop bash -c '
  mkdir -p ~/.ssh && chmod 700 ~/.ssh
  [ -f ~/.ssh/id_rsa ] || ssh-keygen -t rsa -P "" -f ~/.ssh/id_rsa
  cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
  chmod 600 ~/.ssh/authorized_keys
  # trust master/worker1/worker2 host keys ahead of time
  ssh-keyscan -H master worker1 worker2 >> ~/.ssh/known_hosts 2>/dev/null || true
'
echo
echo ">>> COPY THIS PUBLIC KEY <<<"
sudo -u hadoop cat /home/hadoop/.ssh/id_rsa.pub
echo ">>> Then run 03-worker-setup.sh on each worker, pasting the key when prompted."
echo

read -p "Press ENTER once you've added the key to both workers... "

echo "[2/7] Hadoop XML configs"
HCONF=/opt/hadoop/etc/hadoop

sudo -u hadoop tee $HCONF/core-site.xml >/dev/null <<'EOF'
<?xml version="1.0"?>
<configuration>
  <property><name>fs.defaultFS</name><value>hdfs://master:9000</value></property>
  <property><name>hadoop.http.staticuser.user</name><value>hadoop</value></property>
</configuration>
EOF

sudo -u hadoop tee $HCONF/hdfs-site.xml >/dev/null <<'EOF'
<?xml version="1.0"?>
<configuration>
  <property><name>dfs.replication</name><value>2</value></property>
  <property><name>dfs.namenode.name.dir</name><value>/opt/hadoop/data/name</value></property>
  <property><name>dfs.datanode.data.dir</name><value>/opt/hadoop/data/data</value></property>
  <property><name>dfs.webhdfs.enabled</name><value>true</value></property>
  <property><name>dfs.namenode.http-address</name><value>0.0.0.0:9870</value></property>
  <property><name>dfs.namenode.rpc-bind-host</name><value>0.0.0.0</value></property>
</configuration>
EOF

sudo -u hadoop tee $HCONF/workers >/dev/null <<'EOF'
worker1
worker2
EOF

sudo -u hadoop mkdir -p /opt/hadoop/data/name /opt/hadoop/data/data /opt/hadoop/logs

echo "[3/7] push configs to workers"
for h in worker1 worker2; do
  sudo -u hadoop scp -o StrictHostKeyChecking=no \
    $HCONF/core-site.xml $HCONF/hdfs-site.xml $HCONF/workers $HCONF/hadoop-env.sh \
    hadoop@$h:$HCONF/
done

echo "[4/8] format NameNode (idempotent: skips if already formatted)"
# stop any running HDFS first so format/start steps are clean
sudo -u hadoop /opt/hadoop/sbin/stop-dfs.sh || true
if [ ! -f /opt/hadoop/data/name/current/VERSION ]; then
  sudo -u hadoop /opt/hadoop/bin/hdfs namenode -format -nonInteractive -force
fi

echo "[5/8] start HDFS"
sudo -u hadoop /opt/hadoop/sbin/start-dfs.sh
sleep 5
sudo -u hadoop /opt/hadoop/bin/hdfs dfsadmin -report || true

echo "[6/8] create /cloud/blocks in HDFS"
sudo -u hadoop /opt/hadoop/bin/hdfs dfs -mkdir -p /cloud/blocks
sudo -u hadoop /opt/hadoop/bin/hdfs dfs -chmod 777 /cloud/blocks

echo "[7/8] Python venv + controller deps"
cd "$REPO_DIR/controller"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "[8/8] nginx reverse proxy on :80 -> :5000"
sudo apt-get install -y nginx
sudo tee /etc/nginx/sites-available/cloud-controller >/dev/null <<'NGINX'
server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 1024m;          # allow large uploads
    proxy_read_timeout   600;
    proxy_send_timeout   600;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE / streaming
        proxy_buffering          off;
        proxy_request_buffering  off;
        proxy_http_version       1.1;
        proxy_set_header         Connection "";
    }
}
NGINX
sudo ln -sf /etc/nginx/sites-available/cloud-controller /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
sudo systemctl enable nginx

cat <<EOF

==========================================================
HDFS up.       NameNode UI : http://<master-public-ip>:9870
nginx up.      App URL     : http://<master-public-ip>/        (port 80)

To start the cloud controller (keep Flask bound to 127.0.0.1):
  cd $REPO_DIR/controller
  export MASTER_KEY_B64=\$(python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())")
  echo "SAVE THIS KEY: \$MASTER_KEY_B64"
  export WEBHDFS_URL=http://master:9870/webhdfs/v1
  .venv/bin/python app.py
==========================================================
EOF
