"""Shared paths, escaping and small utilities for the WTQ entity research."""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
BASE = RESEARCH.parent                      # /home/aldar/github/wtq-translator
WTQ = BASE / "WikiTableQuestions"           # dataset repo (READ ONLY)
WTQ_TRANSLATOR = BASE / "wtq-translator"    # solution repo (READ ONLY)

SEED = 42
UA = "wtq-entity-research/0.1 (academic entity-translation study; RU fallback)"

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
    """Tiny rate-limited GET with UA, retries and on-disk JSON cache."""

    def __init__(self, cache_name: str, min_interval: float = 0.2):
        self.cache = RESEARCH / "cache" / f"{cache_name}.json"
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.data = json.loads(self.cache.read_text()) if self.cache.exists() else {}
        self.base_interval = min_interval
        self.min_interval = min_interval
        self._last = 0.0
        self.network_errors = {}

    def get_json(self, url: str):
        if url in self.data and "__error__" not in self.data[url]:
            return self.data[url]
        self.data.pop(url, None)  # drop cached errors, retry them
        err = None
        for attempt in range(4):  # bounded: max ~3+6+12=21s backoff per URL
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    obj = json.loads(r.read().decode("utf-8"))
                self.data[url] = obj
                self._save()
                # success: relax pacing slowly back to base
                self.min_interval = max(self.base_interval, self.min_interval * 0.9)
                return obj
            except Exception as e:  # record, back off, keep going
                err = f"{type(e).__name__}: {e}"
                if "429" in err or "503" in err or "502" in err or "timed out" in err or "TimeoutError" in err:
                    # adaptive pacing: slow down globally, then retry
                    self.min_interval = min(self.min_interval * 1.5, 4.0)
                    time.sleep(3 * 2 ** attempt)
                    continue
                break
        self.data[url] = {"__error__": err or "unknown"}
        self._save()
        return self.data[url]

    def _save(self):
        self.cache.write_text(json.dumps(self.data, ensure_ascii=False))


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
