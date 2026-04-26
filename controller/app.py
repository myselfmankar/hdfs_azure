"""Cloud Controller: split -> AES-GCM encrypt -> HDFS via WebHDFS."""
import base64
import hashlib
import io
import json
import os
import uuid

from flask import Flask, request, jsonify, send_file, abort

import config
import crypto_utils
import hdfs_client

app = Flask(__name__)


def _meta_path(file_id: str) -> str:
    return os.path.join(config.META_DIR, f"{file_id}.json")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        abort(400, "missing 'file' field")
    f = request.files["file"]
    filename = f.filename or "unnamed"

    file_id = uuid.uuid4().hex
    hdfs_dir = f"{config.HDFS_BASE_DIR}/{file_id}"
    hdfs_client.mkdirs(hdfs_dir)

    blocks = []
    sha = hashlib.sha256()
    idx = 0
    total = 0

    while True:
        chunk = f.stream.read(config.BLOCK_SIZE)
        if not chunk:
            break
        sha.update(chunk)
        total += len(chunk)

        # AAD binds the block to its file+index so blocks can't be swapped
        aad = f"{file_id}:{idx}".encode()
        nonce, ct = crypto_utils.encrypt(chunk, aad)

        block_name = f"block_{idx:06d}.enc"
        hdfs_client.upload(f"{hdfs_dir}/{block_name}", ct)

        blocks.append({
            "index": idx,
            "name": block_name,
            "nonce": base64.b64encode(nonce).decode(),
            "size": len(chunk),
        })
        idx += 1

    meta = {
        "file_id": file_id,
        "filename": filename,
        "size": total,
        "sha256": sha.hexdigest(),
        "block_size": config.BLOCK_SIZE,
        "hdfs_dir": hdfs_dir,
        "blocks": blocks,
    }
    with open(_meta_path(file_id), "w") as mf:
        json.dump(meta, mf, indent=2)

    return jsonify({"file_id": file_id, "filename": filename, "blocks": len(blocks), "size": total})


@app.route("/download/<file_id>")
def download(file_id):
    if not os.path.exists(_meta_path(file_id)):
        abort(404, "unknown file_id")
    with open(_meta_path(file_id)) as mf:
        meta = json.load(mf)

    buf = io.BytesIO()
    sha = hashlib.sha256()

    for blk in meta["blocks"]:
        ct = hdfs_client.download(f"{meta['hdfs_dir']}/{blk['name']}")
        nonce = base64.b64decode(blk["nonce"])
        aad = f"{file_id}:{blk['index']}".encode()
        pt = crypto_utils.decrypt(nonce, ct, aad)
        sha.update(pt)
        buf.write(pt)

    if sha.hexdigest() != meta["sha256"]:
        abort(500, "integrity check failed")

    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=meta["filename"])


@app.route("/files")
def list_files():
    items = []
    for fname in os.listdir(config.META_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(config.META_DIR, fname)) as mf:
                m = json.load(mf)
            items.append({"file_id": m["file_id"], "filename": m["filename"],
                          "size": m["size"], "blocks": len(m["blocks"])})
    return jsonify(items)


@app.route("/delete/<file_id>", methods=["DELETE"])
def delete(file_id):
    p = _meta_path(file_id)
    if not os.path.exists(p):
        abort(404)
    with open(p) as mf:
        meta = json.load(mf)
    hdfs_client.delete(meta["hdfs_dir"])
    os.remove(p)
    return {"deleted": file_id}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
