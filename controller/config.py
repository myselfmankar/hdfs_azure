import os

# WebHDFS endpoint of the NameNode (use private IP on the master VM, public if remote)
WEBHDFS_URL   = os.environ.get("WEBHDFS_URL", "http://master:9870/webhdfs/v1")
HDFS_USER     = os.environ.get("HDFS_USER", "hadoop")
HDFS_BASE_DIR = "/cloud/blocks"

BLOCK_SIZE    = 4 * 1024 * 1024  # 4 MB segments

# 32-byte master key for AES-256-GCM. In production load from KMS / Azure Key Vault.
# Generate once:  python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
MASTER_KEY_B64 = os.environ.get(
    "MASTER_KEY_B64",
    "8Jx0o2Q2vG9pP3l3jK0mYpV8w4qWcQ5sT7yX1nA0bC4="  # DEV ONLY — replace
)

META_DIR = os.path.join(os.path.dirname(__file__), "metadata")
os.makedirs(META_DIR, exist_ok=True)
