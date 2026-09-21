"""Experiment 2 - Wiktionary EN->RU (Matthias Buchmeier DSL .dz).

Preserves multiple senses: each [m1] item becomes a candidate with
sense (English gloss) and POS when available.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # experiments/dictionaries
from common_dict import (norm, load_sample, category_of, strip_dsl_tags,  # noqa
                         cyrillic_runs, write_results, stats_of)

RAW = HERE / "raw" / "en-ru-enwiktionary.dsl.dz"
INDEX = HERE / "cache" / "index.json"


def build_index():
    with gzip.open(RAW, "rb") as f:
        raw = f.read()
    try:
        txt = raw.decode("utf-16")
    except Exception:
        txt = raw.decode("utf-16-le")
    lines = txt.splitlines()
    idx = {}
    cur_head = None
    cur_pos = None
    cur_sense = None
    cur_items = []
    cards = []
    for ln in lines:
        if not ln.strip():
            continue
        if ln.startswith("#"):
            continue
        if not ln.startswith("\t"):
            # flush previous entry
            if cur_head is not None and cur_items:
                k = norm(cur_head)
                idx.setdefault(k, []).extend(cur_items)
            cur_head = ln.strip()
            cur_pos, cur_sense, cur_items = None, None, []
            cards = []
        else:
            card = ln.strip()
            m = re.search(r"\[p\]<?(\w+)>?\[/p\]", card)
            if m:
                cur_pos = m.group(1)
            m2 = re.search(r"\[i\]\(?([^)\]]*)\)?\[/i\]", card)
            if m2 and cur_sense is None:
                cur_sense = m2.group(1).strip()
            if "[m1]" in card or "[m2]" in card:
                t = strip_dsl_tags(card)
                for run in cyrillic_runs(t):
                    run = run.strip(" .,;")
                    if run:
                        cur_items.append({"ru": run, "pos": cur_pos, "sense": cur_sense})
    if cur_head is not None and cur_items:
        k = norm(cur_head)
        idx.setdefault(k, []).extend(cur_items)
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
            "dictionary": "wiktionary",
            "candidates": [{"ru": c["ru"], "count": None, "probability": None,
                            "pos": c.get("pos"), "sense": c.get("sense")} for c in cands],
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
