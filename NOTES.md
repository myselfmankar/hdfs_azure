# Cloud Mini — Infrastructure Notes

Living document. Update as we configure each piece.

================================================================
1. AZURE RESOURCES (from portal screenshots, 2026-04-26)
================================================================

Resource group : hadoop-mp
Region         : Korea Central (Zone 1)
Subscription   : Azure for Students  (c8f51488-9289-4ff6-a1f1-5710ead2c6ca)
OS (all VMs)   : Ubuntu 24.04 LTS
VM size (all)  : Standard B2as v2  (2 vCPU, 8 GiB RAM)
VNet           : vnet-hadoop / default          <-- all 3 VMs in same VNet :)

+-----------+----------+----------------+--------------+-----------------+
| Role      | VM name  | Public IP      | Private IP   | NIC             |
+-----------+----------+----------------+--------------+-----------------+
| master    | master   | 20.41.109.12   | 10.0.0.4     | master796_z1    |
| worker1   | worker-1 | 20.41.117.191  | 10.0.0.5     | worker-1164_z1  |
| worker2   | worker-2 | 20.41.120.156  | 10.0.0.6     | worker-2337_z1  |
+-----------+----------+----------------+--------------+-----------------+

Created:
  master    2026-04-26 05:24 UTC
  worker-1  2026-04-26 05:33 UTC
  worker-2  2026-04-26 05:35 UTC

================================================================
2. NSG RULES (MINIMAL)
================================================================

Intra-VNet traffic is ALREADY allowed by the default rule
"AllowVnetInBound" (priority 65000) on every Azure NSG.
=> master <-> worker-1 <-> worker-2 needs NO config.

We only need ONE rule per VM for laptop access:

+----------+--------------+--------------------------+------+----------+----------------+
| Priority | Source       | Source IP                | Port | Protocol | Name           |
+----------+--------------+--------------------------+------+----------+----------------+
| 100      | IP Addresses | <my laptop public IP>/32 | *    | Any      | AllowMyLaptop  |
+----------+--------------+--------------------------+------+----------+----------------+

Apply this same rule on master, worker-1, worker-2 NSGs.
Covers SSH (22), NameNode UI (9870), Flask controller (5000), everything.

Get laptop IP (PowerShell):
  (Invoke-WebRequest ifconfig.me/ip -UseBasicParsing).Content.Trim()

If your IP changes often, source can be "Any" (less secure; fine for
a short-lived demo cluster you'll delete after grading).

================================================================
3. SSH ACCESS (from my laptop)
================================================================

Key file (local) : <fill in: path to .pem you downloaded when creating VMs>
Default user     : azureuser

ssh -i <key> azureuser@20.41.109.12     # master
ssh -i <key> azureuser@20.41.117.191    # worker-1
ssh -i <key> azureuser@20.41.120.156    # worker-2

If each VM has its own key, note them:
  master   key : ____________________
  worker-1 key : ____________________
  worker-2 key : ____________________

================================================================
4. /etc/hosts ON ALL 3 VMs
================================================================

# Append on every VM
10.0.0.4   master
10.0.0.5   worker1
10.0.0.6   worker2

================================================================
5. HADOOP CLUSTER LAYOUT (planned)
================================================================

master    : NameNode daemon + Flask Cloud Controller (port 5000)
worker-1  : DataNode daemon
worker-2  : DataNode daemon
HDFS user : hadoop
HDFS_HOME : /opt/hadoop
Java      : openjdk-11
Replication : 2
HDFS dir for blocks : /cloud/blocks
Local data dirs     : /opt/hadoop/data/{name,data}

================================================================
6. SECRETS (do NOT commit real values)
================================================================

MASTER_KEY_B64 : <generate on master with:
                  python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())">
WEBHDFS_URL    : http://master:9870/webhdfs/v1
HDFS_USER      : hadoop

================================================================
7. PROGRESS CHECKLIST
================================================================

[x] All 3 VMs in same VNet (vnet-hadoop), distinct private IPs
[ ] One NSG rule per VM: AllowMyLaptop (intra-VNet allowed by default)
[ ] SSH from laptop works to all 3
[ ] Java 11 + Hadoop 3.3.6 installed on all 3
[ ] hadoop user created on all 3
[ ] Password-less SSH master->master, master->worker1, master->worker2
[ ] /etc/hosts updated on all 3
[ ] core-site.xml / hdfs-site.xml / workers configured on master
[ ] Configs scp'd to workers
[ ] hdfs namenode -format
[ ] start-dfs.sh -> http://20.41.109.12:9870 shows 2 live DataNodes
[ ] Python venv + requirements installed on master
[ ] Cloud Controller running on master:5000
[ ] End-to-end upload + download test passes
[ ] Verified blocks on HDFS are AES-GCM ciphertext

================================================================
8. QUICK COPY-PASTE
================================================================

# Get my laptop's public IP (Windows PowerShell):
#   (Invoke-WebRequest ifconfig.me/ip).Content.Trim()

# SSH config block (~/.ssh/config) for convenience:
#
# Host master
#   HostName 20.41.109.12
#   User azureuser
#   IdentityFile ~/.ssh/<key>.pem
# Host worker1
#   HostName 20.41.117.191
#   User azureuser
#   IdentityFile ~/.ssh/<key>.pem
# Host worker2
#   HostName 20.41.120.156
#   User azureuser
#   IdentityFile ~/.ssh/<key>.pem
