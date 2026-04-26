"""Simple CLI client for the cloud controller."""
import argparse
import sys
import requests


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://<master-public-ip>:5000")
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload");   up.add_argument("path")
    dn = sub.add_parser("download"); dn.add_argument("file_id"); dn.add_argument("out")
    sub.add_parser("list")
    rm = sub.add_parser("delete");   rm.add_argument("file_id")

    a = p.parse_args()

    if a.cmd == "upload":
        with open(a.path, "rb") as f:
            r = requests.post(f"{a.server}/upload", files={"file": (a.path, f)})
        print(r.json())
    elif a.cmd == "download":
        r = requests.get(f"{a.server}/download/{a.file_id}", stream=True)
        if r.status_code != 200:
            print(r.text); sys.exit(1)
        with open(a.out, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        print(f"saved -> {a.out}")
    elif a.cmd == "list":
        print(requests.get(f"{a.server}/files").json())
    elif a.cmd == "delete":
        print(requests.delete(f"{a.server}/delete/{a.file_id}").json())


if __name__ == "__main__":
    main()
