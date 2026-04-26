#!/usr/bin/env bash
# Run on ALL 3 VMs (master, worker-1, worker-2) as a sudoer (azureuser).
# Installs Java + Hadoop, creates 'hadoop' user, sets up /etc/hosts.

set -euo pipefail

HADOOP_VERSION="3.3.6"
HADOOP_TGZ="hadoop-${HADOOP_VERSION}.tar.gz"
HADOOP_URL="https://downloads.apache.org/hadoop/common/hadoop-${HADOOP_VERSION}/${HADOOP_TGZ}"

# Private IPs (from NOTES.md). Edit if yours differ.
MASTER_IP="10.0.0.4"
WORKER1_IP="10.0.0.5"
WORKER2_IP="10.0.0.6"

echo "[1/6] apt update + base packages"
sudo apt-get update -y
sudo apt-get install -y openjdk-11-jdk wget python3-pip python3-venv ssh rsync

echo "[2/6] /etc/hosts"
sudo sed -i '/# hadoop-cluster/,/# hadoop-cluster-end/d' /etc/hosts
sudo tee -a /etc/hosts >/dev/null <<EOF
# hadoop-cluster
${MASTER_IP}  master
${WORKER1_IP} worker1
${WORKER2_IP} worker2
# hadoop-cluster-end
EOF

echo "[3/6] hadoop user"
if ! id hadoop >/dev/null 2>&1; then
  sudo adduser --disabled-password --gecos "" hadoop
fi
sudo usermod -aG sudo hadoop
echo "hadoop ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/hadoop >/dev/null

echo "[4/6] download Hadoop ${HADOOP_VERSION}"
if [ ! -d /opt/hadoop ]; then
  cd /tmp
  [ -f "${HADOOP_TGZ}" ] || wget -q "${HADOOP_URL}"
  sudo tar -xzf "${HADOOP_TGZ}" -C /opt
  sudo mv "/opt/hadoop-${HADOOP_VERSION}" /opt/hadoop
fi
sudo chown -R hadoop:hadoop /opt/hadoop

echo "[5/6] env vars in /etc/profile.d/hadoop.sh"
sudo tee /etc/profile.d/hadoop.sh >/dev/null <<'EOF'
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
EOF
sudo chmod +x /etc/profile.d/hadoop.sh

echo "[6/6] hadoop-env.sh JAVA_HOME"
sudo -u hadoop bash -c '
  f=/opt/hadoop/etc/hadoop/hadoop-env.sh
  grep -q "^export JAVA_HOME=" "$f" \
    && sed -i "s|^export JAVA_HOME=.*|export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64|" "$f" \
    || echo "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64" >> "$f"
'

echo "DONE. Log out and back in (or 'source /etc/profile.d/hadoop.sh') to pick up env."
