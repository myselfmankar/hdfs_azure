"""Tiny WebHDFS client. Avoids extra dependencies."""
import requests
from config import WEBHDFS_URL, HDFS_USER


def _url(path: str) -> str:
    return f"{WEBHDFS_URL}{path}"


def mkdirs(path: str) -> None:
    r = requests.put(_url(path), params={"op": "MKDIRS", "user.name": HDFS_USER})
    r.raise_for_status()


def upload(path: str, data: bytes) -> None:
    # WebHDFS create is a 2-step redirect
    r = requests.put(
        _url(path),
        params={"op": "CREATE", "overwrite": "true", "user.name": HDFS_USER},
        allow_redirects=False,
    )
    if r.status_code != 307:
        r.raise_for_status()
    location = r.headers["Location"]
    r2 = requests.put(location, data=data, headers={"Content-Type": "application/octet-stream"})
    r2.raise_for_status()


def download(path: str) -> bytes:
    r = requests.get(
        _url(path),
        params={"op": "OPEN", "user.name": HDFS_USER},
        allow_redirects=True,
    )
    r.raise_for_status()
    return r.content


def delete(path: str) -> None:
    requests.delete(_url(path), params={"op": "DELETE", "recursive": "true", "user.name": HDFS_USER})
