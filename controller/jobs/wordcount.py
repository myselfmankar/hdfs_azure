"""MapReduce-style word count over HDFS-stored encrypted blocks.

Phases:
  - MAP    : decrypt each block on master, tokenize, emit (word, 1)
  - SHUFFLE: group emissions by word
  - REDUCE : sum counts per key
"""
import base64
import collections
import re
import time

import crypto_utils
import hdfs_client

_TOKEN_RE = re.compile(r"[A-Za-z']+")


def run(meta: dict, target_word: str | None, top_n: int, log) -> dict:
    file_id = meta["file_id"]
    target = (target_word or "").lower().strip() or None

    log.log(f"job: word-count over file_id={file_id}  filename={meta['filename']}  "
            f"size={meta['size']} bytes  blocks={len(meta['blocks'])}  replication=2")
    log.log(f"target word: {target!r}" if target else "target word: (none, top-N only)")

    # ----- MAP -----
    log.log("=== MAP phase ===")
    map_outputs: list[dict[str, int]] = []
    total_tokens = 0
    t0 = time.time()
    for blk in meta["blocks"]:
        bt0 = time.time()
        ct = hdfs_client.download(f"{meta['hdfs_dir']}/{blk['name']}")
        nonce = base64.b64decode(blk["nonce"])
        aad = f"{file_id}:{blk['index']}".encode()
        pt = crypto_utils.decrypt(nonce, ct, aad)

        local: dict[str, int] = collections.Counter()
        for tok in _TOKEN_RE.findall(pt.decode("utf-8", errors="ignore").lower()):
            local[tok] += 1
        tokens = sum(local.values())
        total_tokens += tokens
        map_outputs.append(local)
        log.log(f"  map block_{blk['index']:06d}  bytes={len(pt)}  "
                f"tokens={tokens}  unique={len(local)}  "
                f"took={int((time.time()-bt0)*1000)}ms")
    log.log(f"MAP done: {len(map_outputs)} block-outputs, {total_tokens} tokens total, "
            f"{int((time.time()-t0)*1000)}ms")

    # ----- SHUFFLE -----
    log.log("=== SHUFFLE phase ===")
    s0 = time.time()
    shuffled: dict[str, list[int]] = collections.defaultdict(list)
    for partial in map_outputs:
        for k, v in partial.items():
            shuffled[k].append(v)
    log.log(f"SHUFFLE done: {len(shuffled)} unique keys grouped, "
            f"{int((time.time()-s0)*1000)}ms")

    # ----- REDUCE -----
    log.log("=== REDUCE phase ===")
    r0 = time.time()
    reduced: dict[str, int] = {k: sum(vs) for k, vs in shuffled.items()}
    log.log(f"REDUCE done: {len(reduced)} keys summed, "
            f"{int((time.time()-r0)*1000)}ms")

    # ----- result -----
    top = sorted(reduced.items(), key=lambda x: -x[1])[:top_n]
    target_count = reduced.get(target, 0) if target else None

    log.log("=== RESULT ===")
    if target is not None:
        log.log(f"  count of {target!r} = {target_count}")
    log.log(f"  top {top_n} words: " + ", ".join(f"{w}={c}" for w, c in top[:10])
            + (" ..." if len(top) > 10 else ""))

    return {
        "file_id": file_id,
        "filename": meta["filename"],
        "total_tokens": total_tokens,
        "unique_tokens": len(reduced),
        "target_word": target,
        "target_count": target_count,
        "top": [{"word": w, "count": c} for w, c in top],
        "blocks_processed": len(meta["blocks"]),
    }
