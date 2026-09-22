"""Shared paths, escaping and small utilities for the WTQ entity research."""
from __future__ import annotations

import csv
import fcntl
import gzip
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
BASE = RESEARCH.parent                      # /home/aldar/github/wtq-translator
WTQ = BASE / "WikiTableQuestions"           # dataset repo (READ ONLY)
WTQ_TRANSLATOR = BASE / "wtq-translator"    # solution repo (READ ONLY)

SEED = 42
UA = "wtq-entity-research/0.1 (academic entity-translation study; https://github.com/AldarArmaev/wtq_entity_research)"

_WTQ_ESCAPE = {"\\p": "|", "\\n": "\n", "\\\\": "\\"}


def unescape_wtq(s: str) -> str:
    """Reverse WTQ TSV escaping (see dataset README: \\p, \\n, \\\\)."""
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            two = s[i : i + 2]
            if two in _WTQ_ESCAPE:
                out.append(_WTQ_ESCAPE[two])
                i += 2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def read_tagged_data(path: Path):
    """Stream a tagged/data/*.tagged file, yielding dicts."""
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield row


def read_table_tagged(table_id: str):
    """Parse tagged/<N>-tagged/<M>.tagged into (headers, rows) cell dicts."""
    n, m = table_id.split("/")
    p = WTQ / "tagged" / f"{n}-tagged" / f"{m}.tagged"
    headers, rows = [], []
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            r, c = int(row["row"]), int(row["col"])
            if r == -1:
                headers.append({"col": c, "content": row["content"],
                                "nerTags": row["nerTags"].split("|")})
            else:
                rows.append({"row": r, "col": c, "content": row["content"],
                             "nerTags": row["nerTags"].split("|"),
                             "tokens": row["tokens"]})
    rows.sort(key=lambda x: (x["row"], x["col"]))
    return headers, rows


def table_id_from_context(ctx: str) -> str:
    # "csv/204-csv/590.csv" -> "204/590"
    m = re.match(r"csv/(\d+)-csv/(\d+)\.csv", ctx)
    return f"{m.group(1)}/{m.group(2)}"


def page_json(table_id: str) -> dict:
    n, m = table_id.split("/")
    return json.loads((WTQ / "page" / f"{n}-page" / f"{m}.json").read_text(encoding="utf-8"))


def read_csv_table(table_id: str):
    n, m = table_id.split("/")
    p = WTQ / "csv" / f"{n}-csv" / f"{m}.csv"
    with p.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


class Http:
    """Tiny rate-limited GET with UA, retries and on-disk JSON cache.

    Persistence model: the whole cache is kept in memory (``self.data``) and
    the disk file holds a full snapshot of it. Saves happen (a) after every
    successful/error request (throttled to ~2 s apart) and (b) from a
    background dump thread at least every ``dump_interval`` seconds, so even a
    crash during a long backoff or idle stretch loses at most the responses
    fetched since the last dump. All writes are atomic (temp file + rename).
    """

    def __init__(self, cache_name: str, min_interval: float = 0.2,
                 dump_interval: float = 5.0):
        self.cache = RESEARCH / "cache" / f"{cache_name}.json"
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_cache()
        self.base_interval = min_interval
        self.min_interval = min_interval
        self._last = 0.0
        self._last_save = 0.0
        self._last_error = 0.0
        self.fetches = 0        # real request starts (cache hits not counted)
        self.errors = 0         # 429/502/503/timeout observed
        self.t_start = time.time()
        self.network_errors = {}
        self._lock = threading.Lock()
        self._dirty = False             # new records since the last dump
        self._dump_interval = dump_interval
        self._dump_stop = threading.Event()
        # One run per cache at a time: the Wikimedia rate cap is per IP, so two
        # parallel runs of the same experiment would double the request rate
        # and race over the same cache file. flock releases on process exit
        # (even on kill), so a stuck lock cannot survive a dead process.
        self._lockfile = open(self.cache.with_suffix(".lock"), "w")
        try:
            fcntl.flock(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit(f"cache {cache_name} is locked by another running experiment "
                     f"({self._lockfile.name}); wait for it or lower --rpm.")
        threading.Thread(target=self._dump_loop, name="http-cache-dump",
                         daemon=True).start()

    def get_json(self, url: str):
        with self._lock:
            if url in self.data and "__error__" not in self.data[url]:
                return self.data[url]
            self.data.pop(url, None)  # drop cached errors, retry them
        err = None
        for attempt in range(4):  # bounded: max ~3+6+12=21s backoff per URL
            # Global pace gate: each request's start is scheduled at least
            # min_interval after the previous scheduled start. The sleep runs
            # OUTSIDE the lock, so concurrent callers overlap only network
            # latency and never raise the aggregate request rate (that is what
            # would get the client rate-limited or blocked).
            now = time.time()
            with self._lock:
                target = max(self._last + self.min_interval, now)
                self._last = target
                self.fetches += 1  # a request is about to be started
            wait = target - now
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Encoding": "gzip"})
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    raw = r.read()
                    if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                        raw = gzip.decompress(raw)
                    obj = json.loads(raw.decode("utf-8"))
                now = time.time()
                with self._lock:
                    self.data[url] = obj
                    self._dirty = True
                    self._save()
                    # success: relax pacing slowly back to base, but only once
                    # ~30s passed since the last error so a 429 burst has time
                    # to clear instead of the interval oscillating up-down
                    if now - self._last_error > 30.0:
                        self.min_interval = max(self.base_interval, self.min_interval * 0.9)
                return obj
            except urllib.error.HTTPError as e:
                err = f"HTTPError: {e.code} {e.reason}"
                if e.code in (429, 502, 503):
                    ra = e.headers.get("Retry-After") if e.headers else None
                    with self._lock:
                        self.errors += 1
                        self._last_error = time.time()
                        self.min_interval = min(self.min_interval * 1.5, 4.0)
                    delay = 3 * 2 ** attempt
                    if ra and ra.isdigit():
                        delay = max(delay, int(ra))
                    time.sleep(delay)
                    continue
                break
            except Exception as e:  # record, back off, keep going
                err = f"{type(e).__name__}: {e}"
                if "429" in err or "503" in err or "502" in err or "timed out" in err or "TimeoutError" in err:
                    # adaptive pacing: slow down globally, then retry
                    with self._lock:
                        self.errors += 1
                        self._last_error = time.time()
                        self.min_interval = min(self.min_interval * 1.5, 4.0)
                    time.sleep(3 * 2 ** attempt)
                    continue
                break
        with self._lock:
            self.data[url] = {"__error__": err or "unknown"}
            self._dirty = True
            self._save(force=True)
        return self.data[url]

    def _load_cache(self) -> dict:
        """Read the on-disk JSON cache; never crash on a corrupt/absent file.

        The HTTP cache is pure optimization: responses are fetched again on a
        miss. So a 0-byte or truncated cache must not kill the run. The broken
        file is moved aside (not deleted) under a timestamped name so it can be
        inspected or manually repaired, and the run continues with an empty
        cache instead of aborting.
        """
        if not self.cache.exists():
            return {}
        try:
            data = json.loads(self.cache.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not a JSON object")
            return data
        except ValueError as e:
            print(f"warn: cache {self.cache} unreadable ({e}); "
                  f"moving it aside and starting with an empty cache",
                  file=sys.stderr)
            try:
                bak = self.cache.with_suffix(
                    f"{self.cache.suffix}.corrupt-{int(time.time())}")
                self.cache.replace(bak)
                print(f"warn: broken cache kept at {bak}", file=sys.stderr)
            except OSError:
                pass
            return {}

    def _save(self, force: bool = False):
        # Throttle full-dict flushes: the cache grows with the workload and
        # rewriting the whole JSON on every request is O(n^2) I/O. Error paths
        # force a flush so failures are persisted promptly.
        now = time.time()
        if not force and now - self._last_save < 2.0:
            return
        self._last_save = now
        # Atomic replace, not in-place truncate: Path.write_text() on the real
        # path opens with "w" (truncates to 0 bytes) *before* writing, so a
        # kill/crash mid-write left a 0-byte cache and the whole collected
        # data was lost on restart. Writing a temp file in the same directory
        # and renaming it over the cache keeps the file either fully old or
        # fully new — never partial. A crash mid-write can only corrupt the
        # temp file, never the cache.
        tmp = self.cache.with_suffix(f"{self.cache.suffix}.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False),
                       encoding="utf-8")
        try:
            with tmp.open("rb") as f:
                os.fsync(f.fileno())
            os.replace(tmp, self.cache)
        except OSError:
            # Keep the pre-fix in-place behavior as a fallback only: still
            # better to have *tried* the atomic rename and failed than to
            # propagate the exception and abort the request handling.
            self.cache.write_text(json.dumps(self.data, ensure_ascii=False),
                                  encoding="utf-8")
        try:
            # Persist the directory entry so a rename isn't lost on power loss.
            dfd = os.open(str(self.cache.parent), os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass

    def _dump_loop(self):
        """Background safety net for regular cache dumps.

        Event-driven saves in get_json only run when a request completes, so a
        run sitting in a long backoff (429/502/503/timeout) or otherwise idle
        would leave freshly fetched records only in memory. This thread forces
        a full snapshot at least every ``dump_interval`` seconds whenever new
        records arrived (dirty flag keeps it from rewriting the file when
        nothing changed). This bounds the data lost to a hard kill to at most
        one dump interval. The thread is a daemon: a normal process exit (or
        the finally flush) writes the final state, and a crash simply kills it.
        """
        while not self._dump_stop.wait(self._dump_interval):
            with self._lock:
                if self._dirty:
                    self._dirty = False
                    try:
                        self._save(force=True)
                    except Exception:
                        # Disk trouble: keep the flag set so the next tick
                        # retries instead of silently dropping new records.
                        self._dirty = True

    def flush(self):
        with self._lock:
            self._save(force=True)

    def stats(self):
        """Load counters for measuring the achieved request rate (rpm)."""
        with self._lock:
            return {"fetches": self.fetches, "errors": self.errors,
                    "interval": self.min_interval, "t_start": self.t_start}


def norm_key(s: str) -> str:
    return " ".join(s.split()).strip().casefold()


def jdump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def jload(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def jdumpl(path: Path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
