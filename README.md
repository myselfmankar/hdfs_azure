# Mini SaaS Cloud over HDFS

3 Azure VMs:
- **master**: NameNode + Flask Cloud Controller
- **worker1, worker2**: DataNodes

Client uploads a file → controller splits into 4 MB blocks → AES-256-GCM encrypts each block (random nonce, AAD = file_id:index) → stores via WebHDFS. Metadata (block list, nonces, sha256) kept locally on master in `controller/metadata/`.

## Run controller (on master)
```bash
cd controller
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export MASTER_KEY_B64=$(python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())")
export WEBHDFS_URL=http://master:9870/webhdfs/v1
python app.py
```

## Use from your laptop
```bash
python client/cloud_cli.py --server http://<master-public-ip>:5000 upload bigfile.zip
python client/cloud_cli.py --server http://<master-public-ip>:5000 list
python client/cloud_cli.py --server http://<master-public-ip>:5000 download <file_id> out.zip
```

## Verify blocks on HDFS
```bash
hdfs dfs -ls -R /cloud/blocks
```
You'll see encrypted `block_000000.enc` files; `cat`-ing them shows ciphertext.
