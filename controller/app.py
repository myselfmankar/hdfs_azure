"""Cloud Controller: split -> AES-GCM encrypt -> HDFS via WebHDFS.

Routes:
  GET    /                         -> SPA
  GET    /api/health
  POST   /api/upload               -> {job_id}; logs streamed via SSE
  GET    /api/files
  GET    /api/files/<id>           -> full meta (block list)
  GET    /api/download/<id>        -> decrypted file
  DELETE /api/files/<id>
  POST   /api/jobs/wordcount       -> {job_id}
  GET    /api/jobs/<job_id>/stream -> Server-Sent Events
"""
import base64
import hashlib
import io
import json
import os
import threading
import uuid

from flask import Flask, Response, request, jsonify, send_file, abort, send_from_directory

import config
import crypto_utils
import hdfs_client
import log_stream
from jobs import wordcount

app = Flask(__name__, static_folder="static", static_url_path="/static")


def _meta_path(file_id: str) -> str:
    return os.path.join(config.META_DIR, f"{file_id}.json")


def _load_meta(file_id: str) -> dict:
    p = _meta_path(file_id)
    if not os.path.exists(p):
        abort(404, "unknown file_id")
    with open(p) as mf:
        return json.load(mf)


def _human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


# ---- SPA ---------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return {"status": "ok"}


# ---- upload (background thread, SSE-friendly) --------------------
def _do_upload(file_bytes: bytes, filename: str, log: log_stream.JobLog):
    try:
        file_id = uuid.uuid4().hex
        hdfs_dir = f"{config.HDFS_BASE_DIR}/{file_id}"

        log.log(f"received '{filename}' size={_human(len(file_bytes))} ({len(file_bytes)} bytes)")
        log.log(f"file_id={file_id}  block_size={_human(config.BLOCK_SIZE)}  replication=2")

        log.log(f"HDFS mkdir {hdfs_dir}")
        hdfs_client.mkdirs(hdfs_dir)

        n_blocks = max(1, (len(file_bytes) + config.BLOCK_SIZE - 1) // config.BLOCK_SIZE)
        log.log(f"=== SPLIT phase: {n_blocks} block(s) ===")

        blocks = []
        sha = hashlib.sha256()
        for idx in range(n_blocks):
            chunk = file_bytes[idx * config.BLOCK_SIZE:(idx + 1) * config.BLOCK_SIZE]
            sha.update(chunk)

            aad = f"{file_id}:{idx}".encode()
            nonce, ct = crypto_utils.encrypt(chunk, aad)
            block_name = f"block_{idx:06d}.enc"

            log.log(f"  block {idx:06d}: plain={_human(len(chunk))}  "
                    f"AES-256-GCM nonce={base64.b64encode(nonce).decode()}  "
                    f"cipher={_human(len(ct))} (incl 16B tag)")
            log.log(f"    PUT WebHDFS {hdfs_dir}/{block_name}")
            hdfs_client.upload(f"{hdfs_dir}/{block_name}", ct)
            log.log(f"    OK  HDFS replicated to: worker1, worker2")

            blocks.append({"index": idx, "name": block_name,
                           "nonce": base64.b64encode(nonce).decode(),
                           "size": len(chunk)})

        meta = {"file_id": file_id, "filename": filename,
                "size": len(file_bytes), "sha256": sha.hexdigest(),
                "block_size": config.BLOCK_SIZE, "hdfs_dir": hdfs_dir,
                "blocks": blocks}
        with open(_meta_path(file_id), "w") as mf:
            json.dump(meta, mf, indent=2)

        log.log(f"metadata saved: sha256={meta['sha256']}")
        log.log("=== UPLOAD COMPLETE ===")
        log.finish({"file_id": file_id, "filename": filename,
                    "size": len(file_bytes), "blocks": len(blocks)})
    except Exception as e:
        log.log(f"ERROR: {e}")
        log.finish({"error": str(e)})


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        abort(400, "missing 'file' field")
    f = request.files["file"]
    filename = f.filename or "unnamed"
    data = f.stream.read()
    log = log_stream.create()
    threading.Thread(target=_do_upload, args=(data, filename, log), daemon=True).start()
    return jsonify({"job_id": log.id})


# ---- download / list / delete -----------------------------------
@app.route("/api/download/<file_id>")
def download(file_id):
    meta = _load_meta(file_id)
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


@app.route("/api/files")
def list_files():
    items = []
    for fname in sorted(os.listdir(config.META_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(config.META_DIR, fname)) as mf:
                m = json.load(mf)
            items.append({"file_id": m["file_id"], "filename": m["filename"],
                          "size": m["size"], "blocks": len(m["blocks"]),
                          "sha256": m["sha256"]})
    return jsonify(items)


@app.route("/api/files/<file_id>")
def file_meta(file_id):
    meta = _load_meta(file_id)
    return jsonify({
        "file_id": meta["file_id"], "filename": meta["filename"],
        "size": meta["size"], "sha256": meta["sha256"],
        "block_size": meta["block_size"], "hdfs_dir": meta["hdfs_dir"],
        "blocks": [{"index": b["index"], "name": b["name"], "size": b["size"]}
                   for b in meta["blocks"]],
    })


@app.route("/api/files/<file_id>", methods=["DELETE"])
def delete(file_id):
    meta = _load_meta(file_id)
    hdfs_client.delete(meta["hdfs_dir"])
    os.remove(_meta_path(file_id))
    return {"deleted": file_id}


# ---- word-count job ---------------------------------------------
def _do_wordcount(meta, target_word, top_n, log):
    try:
        result = wordcount.run(meta, target_word, top_n, log)
        log.finish(result)
    except Exception as e:
        log.log(f"ERROR: {e}")
        log.finish({"error": str(e)})


@app.route("/api/jobs/wordcount", methods=["POST"])
def submit_wordcount():
    body = request.get_json(force=True) or {}
    file_id = body.get("file_id")
    target_word = body.get("target_word")
    top_n = int(body.get("top_n", 20))
    if not file_id:
        abort(400, "file_id required")
    meta = _load_meta(file_id)
    log = log_stream.create()
    threading.Thread(target=_do_wordcount,
                     args=(meta, target_word, top_n, log), daemon=True).start()
    return jsonify({"job_id": log.id})


# ---- SSE log stream ---------------------------------------------
@app.route("/api/jobs/<job_id>/stream")
def stream(job_id):
    job = log_stream.get(job_id)
    if job is None:
        abort(404, "unknown job_id")

    def gen():
        while True:
            evt = job.q.get()
            yield f"data: {json.dumps(evt)}\n\n"
            if evt["msg"] == "__done__":
                break

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
