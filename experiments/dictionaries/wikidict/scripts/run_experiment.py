"""Experiment 1 - Wikidict EN->RU (Wikidata/interwiki derived, DSL UTF-8).

Builds a normalized-EN -> RU index from data DSL, runs the 200-sample lookup.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common_dict import (ROOT, norm, load_sample, category_of, context_of,  # noqa
                         parse_dsl_cards, strip_dsl_tags, write_results, stats_of)

RAW = HERE / "raw" / "en-ru_wikidict.dsl"
INDEX = HERE / "cache" / "index.json"


def build_index():
    lines = RAW.read_text(encoding="utf-8", errors="replace").splitlines()
    idx = {}
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if not ln.strip() or ln.startswith("#"):
            i += 1
            continue
        if ln.startswith("\t") or ln.startswith(" "):
            i += 1
            continue
        head = ln.strip()
        ru = ""
        j = i + 1
        # RU line: next non-empty, non-indented, Cyrillic line (this dict: 1 line)
        while j < n and not lines[j].strip():
            j += 1
        if j < n and not lines[j].startswith(("\t", " ")) and re.search(r"[А-Яа-яЁё]", lines[j]):
            ru = " ".join(lines[j].split())
        if ru:
            k = norm(head.replace("{{", "").replace("}}", ""))
            idx.setdefault(k, []).append({
                "ru": ru,
                "card": f"{head}: {ru}"[:160],
            })
        i = j if ru else i + 1
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(idx, ensure_ascii=False))
    return len(idx)


def main():
    if not INDEX.exists():
        n = build_index()
        print("index keys:", n, flush=True)
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
            "dictionary": "wikidict",
            "candidates": [{"ru": c["ru"], "count": None, "probability": None,
                            "pos": None, "sense": None} for c in cands],
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
    print(json.dumps(st, ensure_ascii=False, indent=1)[:1500])


if __name__ == "__main__":
    main()
