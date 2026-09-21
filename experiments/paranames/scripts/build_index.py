"""Build ParaNames EN->RU index by a single streaming pass of the gz TSV.

Output: cache file `paranames_en_ru.jsonl` keyed by normalized English name.
Also: total records / number of distinct entities / ru-rows / type distribution.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RAW = HERE / "raw" / "paranames.tsv.gz"
OUT = HERE / "cache" / "paranames_en_ru.jsonl"
STATS = HERE / "cache" / "paranames_stats.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    s = s.replace("’", "'").replace("–", "-").replace("—", "-")
    return " ".join(s.split()).casefold().strip()


def main():
    stats = defaultdict(int)
    types = defaultdict(int)
    ru_by_key = defaultdict(list)
    eng_rows_recent = 0
    t0 = time.time()
    with gzip.open(RAW, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline()
        for line in f:
            line = line.rstrip("\n\r")
            if not line:
                continue
            p = line.split("\t")
            if len(p) != 5:
                stats["malformed"] += 1
                continue
            qid, eng, label, lang, typ = p
            stats["total_records"] += 1
            types[typ] += 1
            if lang == "en":
                stats["en_rows"] += 1
            elif lang == "ru":
                ru_by_key[norm(eng)].append({
                    "ru": label, "qid": qid, "type": typ,
                    "eng_canonical": eng,
                })
                stats["ru_rows"] += 1
            eng_rows_recent += 1
            if eng_rows_recent >= 5_000_000:
                print("progress", stats["total_records"], "rows,", int(time.time() - t0), "s", flush=True)
                eng_rows_recent = 0
    # write index
    n_keys = 0
    with OUT.open("w", encoding="utf-8") as f:
        for k, lst in ru_by_key.items():
            f.write(json.dumps({"key": k, "cands": lst}, ensure_ascii=False) + "\n")
            n_keys += 1
    meta = {
        "total_records": stats["total_records"],
        "en_rows": stats["en_rows"],
        "ru_rows": stats["ru_rows"],
        "distinct_en_keys_with_ru": n_keys,
        "type_distribution": dict(types),
        "elapsed_s": round(time.time() - t0, 1),
    }
    STATS.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
