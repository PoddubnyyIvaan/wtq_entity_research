"""Experiment 3 - OpenRussian (Badestrand/russian-dictionary CSVs, CC BY-SA 4.0).

Reverse index: each English gloss (from translations_en column) -> Russian word.
Accent marks ('/ˈ) are stripped from the Russian side only at index time;
original word kept in `accented` when present.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common_dict import norm, load_sample, category_of, write_results, stats_of  # noqa

FILES = ["nouns.csv", "verbs.csv", "adjectives.csv", "others.csv"]
INDEX = HERE / "cache" / "index.json"


def deaccent(s: str) -> str:
    s = s.replace("’", "").replace("'", "").replace("ˈ", "").replace("\u0301", "")
    return " ".join(s.split())


def split_glosses(translations_en: str):
    parts = re.split(r"[;,/]|\s\|\s", translations_en)
    return [g.strip().strip("()") for g in parts if g.strip()]


def build_index():
    idx = {}
    meta = {}
    for f in FILES:
        p = HERE / "raw" / f
        with p.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                word = deaccent(row.get("bare") or "")
                if not word:
                    continue
                for g in split_glosses(row.get("translations_en") or ""):
                    k = norm(g)
                    if not k or not re.search(r"[A-Za-z]", k):
                        continue
                    idx.setdefault(k, []).append({"ru": word})
                    meta.setdefault(k, {"pos": [], "count": 0})["pos"].append(
                        {"nouns": "noun", "verbs": "verb", "adjectives": "adj"}.get(f, "other"))
                    meta[k]["count"] += 1
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(idx, ensure_ascii=False))
    return len(idx), sum(len(v) for v in idx.values())


def main():
    if not INDEX.exists():
        nk, nc = build_index()
        print("index keys:", nk, "items:", nc, flush=True)
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    rows = []
    for it in load_sample():
        key = norm(it["cell_value"])
        cands = idx.get(key, [])
        mt = "none" if not cands else "single" if len(cands) == 1 else "multiple"
        rows.append({
            "id": it["example_id"],
            "source_surface": it["cell_value"],
            "normalized_surface": key,
            "category": category_of(it),
            "entity_type": it["candidate_type"],
            "context": {
                "column": it["column_header"],
                "row": " | ".join(v for v in it["row_context"].values() if v)[:200],
                "question": it["question_context"] or None,
            },
            "dictionary": "openrussian",
            "candidates": [{"ru": c["ru"], "count": None, "probability": None,
                            "pos": "noun" if True else None, "sense": None} for c in cands],
            "candidate_count": len(cands),
            "match_type": mt,
            "selected": cands[0]["ru"] if mt == "single" else None,
            "decision": {"none": "NO_MATCH", "single": "SINGLE_CANDIDATE",
                         "multiple": "MULTIPLE"}[mt],
            "reason": "dictionary_lookup_only",
        })
    write_results(HERE / "results.jsonl", rows)
    st = stats_of(rows)
    (HERE / "stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
    print(json.dumps(st, ensure_ascii=False, indent=1)[:1200])


if __name__ == "__main__":
    main()
