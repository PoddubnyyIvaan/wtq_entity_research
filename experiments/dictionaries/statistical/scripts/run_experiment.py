"""Experiment 4 - Statistical EN->RU dictionaries (KvaytG, parquet).

4A full (56 624 entries) and 4B filtered (4 096 entries) run separately.
Candidates carry count/probability; top-1-by-probability recorded separately
from naive first candidate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common_dict import norm, load_sample, category_of, write_results, stats_of  # noqa

SOURCES = {
    "full": (HERE / "raw" / "statistical_full.parquet", HERE / "results_full.jsonl",
             HERE / "cache" / "index_full.json"),
    "filtered": (HERE / "raw" / "statistical_filtered.parquet", HERE / "results_filtered.jsonl",
                 HERE / "cache" / "index_filtered.json"),
}


def build_index(src):
    t = pq.read_table(src).to_pylist()
    idx = {}
    for row in t:
        k = norm(row["english_word"])
        if not k:
            continue
        idx.setdefault(k, []).append({
            "ru": row["russian_word"],
            "count": row["count"],
            "probability": row["probability"],
        })
    # stable: sort by probability desc
    for v in idx.values():
        v.sort(key=lambda c: -(c["probability"] or 0))
    return idx


def main():
    for variant, (src, res, cache) in SOURCES.items():
        if not cache.exists():
            idx = build_index(src)
            cache.write_text(json.dumps(idx, ensure_ascii=False))
        idx = json.loads(cache.read_text(encoding="utf-8"))
        rows = []
        probs = []
        for it in load_sample():
            key = norm(it["cell_value"])
            cands = idx.get(key, [])
            mt = "none" if not cands else "single" if len(cands) == 1 else "multiple"
            top1 = (cands[0]["probability"] if cands else None)
            if cands:
                probs.append(top1)
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
                "dictionary": f"statistical_{cache.stem}",
                "candidates": cands,
                "candidate_count": len(cands),
                "match_type": mt,
                "selected": (cands[0]["ru"] if mt == "single" else
                             cands[0]["ru"] if mt == "multiple" else None),
                "top1_probability": top1,
                "decision": {"none": "NO_MATCH", "single": "SINGLE_CANDIDATE",
                             "multiple": "MULTIPLE"}[mt],
                "reason": "dictionary_lookup_only; top1 by probability (not selected automatically)",
            })
        write_results(res, rows)
        st = stats_of(rows, extra={
            "mean_candidate_count": (sum(r["candidate_count"] for r in rows if r["candidate_count"]) /
                                     max(1, sum(1 for r in rows if r["candidate_count"]))),
            "mean_top1_probability": (sum(probs) / len(probs)) if probs else None,
        })
        (HERE / f"stats_{cache.stem}.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
        print(cache.name, json.dumps({k: st[k] for k in ("total", "match_type", "decision")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
