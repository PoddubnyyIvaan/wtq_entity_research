"""Build a targeted QID -> RU-name lookup from ParaNames for a fixed QID list."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import RESEARCH  # noqa

RAW = HERE / "raw" / "paranames.tsv.gz"
KNOWN = {r["qid"] for r in (json.loads(l) for l in (ROOT / "results" / "exp2_wikidata.jsonl").open()) if r["qid"]}
OUT = HERE / "cache" / "paranames_by_qid.json"


def main():
    ru = {}
    with gzip.open(RAW, "rt", encoding="utf-8", errors="replace") as f:
        f.readline()
        for line in f:
            p = line.rstrip("\n\r").split("\t")
            if len(p) != 5 or p[3] != "ru":
                continue
            if p[0] in KNOWN:
                ru.setdefault(p[0], []).append({"ru": p[2], "type": p[4], "eng_canonical": p[1]})
    OUT.write_text(json.dumps(ru, ensure_ascii=False))
    print("qids with ru in paranames:", len(ru), "of", len(KNOWN))


if __name__ == "__main__":
    main()
