"""Special WTQ cases + dictionary probes; union/intersection/agreement analysis."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_dict import norm  # noqa

DICTS = {
    "wikidict": HERE / "wikidict" / "cache" / "index.json",
    "wiktionary": HERE / "wiktionary" / "cache" / "index.json",
    "openrussian": HERE / "openrussian" / "cache" / "index.json",
    "statistical_full": HERE / "statistical" / "cache" / "index_full.json",
    "statistical_filtered": HERE / "statistical" / "cache" / "index_filtered.json",
}

MANDATORY = ["Smith", "Smyth", "New York", "London", "George", "Arsenal", "Washington",
             "Yinchuan", "Red Box", "@ Giants", "National Football League Round 6",
             "current", "Ha-218", "Fashion Magazine", "Student/Model", "Allsvenskan",
             "Toronto Maple Leafs", "Cooper-Maserati"]
SPECIAL = ["book", "current", "bank", "match", "round", "record", "field",
           "Smith", "London", "George", "Washington", "New York"]

SAMPLE_VALUES = set()
for l in (Path(__file__).resolve().parents[3] / "samples" / "sample200.jsonl").open():
    SAMPLE_VALUES.add(json.loads(l)["cell_value"].strip().casefold())


def main():
    idx = {d: json.loads(p.read_text(encoding="utf-8")) for d, p in DICTS.items()}
    out = {"special_probes": {}, "sample_cases": {}, "agreement": {}, "union_coverage": {}}

    # dictionary probes for mandatory words not present in the sample
    for w in SPECIAL:
        k = norm(w)
        out["special_probes"][w] = {d: [c["ru"] for c in idx[d].get(k, [])][:6] for d in idx}

    # mandatory cases found/not found in the sample
    for m in MANDATORY:
        out["sample_cases"][m] = ("FOUND" if m.strip().casefold() in
                                  {v.casefold() for v in SAMPLE_VALUES} else "NOT_FOUND_IN_SAMPLE")

    # per-occurrence candidate sets (normalized) from each dict's results
    res = {}
    for d in ["wikidict", "wiktionary", "openrussian"]:
        rows = [json.loads(l) for l in (HERE / d / "results.jsonl").open()]
        res[d] = {r["id"]: {" ".join(c["ru"].split()).casefold() for c in r["candidates"]} for r in rows}
    for d, variant in [("statistical_full", "full.jsonl"), ("statistical_filtered", "filtered.jsonl")]:
        rows = [json.loads(l) for l in (HERE / "statistical" / f"results_{variant}").open()]
        res[d] = {r["id"]: {" ".join(c["ru"].split()).casefold() for c in r["candidates"]} for r in rows}

    # agreement on the intersection of matched occurrences
    agree = Counter()
    n_pairs = Counter()
    dicts = list(res)
    occ_by_id = defaultdict(dict)
    for d, m in res.items():
        for rid, cands in m.items():
            occ_by_id[rid][d] = cands
    for rid, per in occ_by_id.items():
        for i, da in enumerate(dicts):
            for db in dicts[i + 1:]:
                a, b = per.get(da), per.get(db)
                if not a or not b:
                    continue
                n_pairs[(da, db)] += 1
                agree[(da, db)] += int(bool(a & b))
    out["pairwise_agreement"] = {
        f"{da} vs {db}": {"overlapping_occurrences": n, "agreeing": agree[(da, db)],
                          "rate": round(agree[(da, db)] / n, 2)}
        for (da, db), n in n_pairs.items() if n
    }

    # union / intersection coverage per occurrence
    union_hit = 0
    inter2_hit = 0
    n_any = 0
    union_examples = {}
    for rid, per in occ_by_id.items():
        any_cands = set()
        for d, cands in per.items():
            any_cands |= cands
        if any_cands:
            union_hit += 1
            src = [r for r in rows if r["id"] == rid][0]["source_surface"]
            union_examples[rid] = {"surface": src, "union": sorted(any_cands, key=str.casefold)[:8],
                                   "per_dict": {d: sorted(cands)[:4] for d, cands in per.items()}}
        matched_any = {d for d, cands in per.items() if cands}
        if len(matched_any) >= 2:
            inter2_hit += 1
    out["union_coverage"] = {
        "occurrences_with_any_dict_match": union_hit,
        "occurrences_matched_by_ge2": inter2_hit,
        "examples": union_examples,
    }
    (HERE / "COMPARISON_ANALYSIS.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: out[k] for k in ("pairwise_agreement", "union_coverage")},
                     ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
