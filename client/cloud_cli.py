"""Simple CLI client for the cloud controller."""
import argparse
import json
import sys
import requests


def _tail(server, job_id):
    with requests.get(f"{server}/api/jobs/{job_id}/stream", stream=True) as r:
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            evt = json.loads(line[6:])
            if evt.get("msg") == "__done__":
                return evt.get("result")
            print(f"[{evt['ts']}] {evt['msg']}")
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://<master-public-ip>:5000")
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload");   up.add_argument("path")
    dn = sub.add_parser("download"); dn.add_argument("file_id"); dn.add_argument("out")
    sub.add_parser("list")
    rm = sub.add_parser("delete");   rm.add_argument("file_id")
    wc = sub.add_parser("wordcount"); wc.add_argument("file_id"); wc.add_argument("--word", default=None); wc.add_argument("--top", type=int, default=20)

    a = p.parse_args()

    if a.cmd == "upload":
        with open(a.path, "rb") as f:
            r = requests.post(f"{a.server}/api/upload", files={"file": (a.path, f)})
        job = r.json()["job_id"]
        result = _tail(a.server, job)
        print("\nresult:", result)
    elif a.cmd == "download":
        r = requests.get(f"{a.server}/api/download/{a.file_id}", stream=True)
        if r.status_code != 200:
            print(r.text); sys.exit(1)
        with open(a.out, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        print(f"saved -> {a.out}")
    elif a.cmd == "list":
        print(json.dumps(requests.get(f"{a.server}/api/files").json(), indent=2))
    elif a.cmd == "delete":
        print(requests.delete(f"{a.server}/api/files/{a.file_id}").json())
    elif a.cmd == "wordcount":
        body = {"file_id": a.file_id, "target_word": a.word, "top_n": a.top}
        r = requests.post(f"{a.server}/api/jobs/wordcount", json=body)
        job = r.json()["job_id"]
        result = _tail(a.server, job)
        print("\nresult:", json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
