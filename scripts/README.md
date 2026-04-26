# Setup runbook

## 0. Push this repo to GitHub (from your laptop)

```powershell
cd D:\_projects\cloud_mini
git init
git branch -M main
git add .
git commit -m "initial"
# create empty repo on github.com first, then:
git remote add origin https://github.com/<you>/cloud-mini.git
git push -u origin main
```

## 1. On EACH VM (master, worker-1, worker-2)

```bash
sudo apt-get install -y git
git clone https://github.com/<you>/cloud-mini.git
cd cloud-mini
chmod +x scripts/*.sh
./scripts/01-common-setup.sh
```

## 2. On master only

```bash
cd ~/cloud-mini
./scripts/02-master-setup.sh
```
The script will print the hadoop user's public key and pause. Keep this terminal open.

## 3. On EACH worker (in a second SSH session)

```bash
cd ~/cloud-mini
./scripts/03-worker-setup.sh
# paste the public key from step 2, then Ctrl-D
```

## 4. Back on master

Press ENTER to continue script 02. It will format HDFS, start the cluster, and install Python deps.

Open `http://<master-public-ip>:9870` — should show 2 live DataNodes.

## 5. Start the cloud controller (master)

Follow the final printout from script 02 (sets `MASTER_KEY_B64`, runs Flask).

## 6. Test from your laptop

```powershell
python client/cloud_cli.py --server http://<master-public-ip>:5000 upload some-file.zip
python client/cloud_cli.py --server http://<master-public-ip>:5000 list
python client/cloud_cli.py --server http://<master-public-ip>:5000 download <file_id> out.zip
```

## Updating code later

After pushing changes from your laptop:
```bash
ssh azureuser@master "cd ~/cloud-mini && git pull"
# restart the controller
```
