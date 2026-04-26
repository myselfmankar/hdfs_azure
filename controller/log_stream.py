"""Per-job in-memory log streams for SSE."""
import queue
import threading
import time
import uuid


class JobLog:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.q: "queue.Queue[dict]" = queue.Queue()
        self.done = False
        self.result = None

    def log(self, msg: str, **extra):
        ts = time.strftime("%H:%M:%S")
        self.q.put({"ts": ts, "msg": msg, **extra})

    def finish(self, result=None):
        self.result = result
        self.done = True
        self.q.put({"ts": time.strftime("%H:%M:%S"), "msg": "__done__", "result": result})


_jobs: "dict[str, JobLog]" = {}
_lock = threading.Lock()


def create() -> JobLog:
    j = JobLog()
    with _lock:
        _jobs[j.id] = j
    return j


def get(job_id: str) -> JobLog | None:
    return _jobs.get(job_id)
