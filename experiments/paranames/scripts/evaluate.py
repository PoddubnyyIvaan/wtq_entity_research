"""Aggregate evaluation for the ParaNames experiment.

Produces: explore stats json + human-verification table skeleton for the
40 reused manual cases and the mandatory cases; writes results into
`paranames_eval.json`.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    s = re.sub(r"\s+", " ", s.replace("’", "'")).casefold().strip()
    return s


def main():
    rows = [json.loads(l) for l in (HERE / "paranames_results.jsonl").open()]
    # agreement PN vs Wikidata where identities known (qid present in both)
    pn_qid_pairs = []
    exact_same_qid = 0
    for r in rows:
        if not r["paranames_candidates"] or not r["qid"]:
            continue
        for c in r["paranames_candidates"]:
            if c.get("qid") == r["qid"]:
                pn_qid_pairs.append(r)
                form_equal = norm(c["ru"]) == norm(r["wikidata_ru"]) if r["wikidata_ru"] else False
                exact_same_qid += int(form_equal)
    stats = {
        "identity_path_cases": {
            "qid_present": sum(1 for r in rows if r["qid"]),
            "pn_has_ru_for_same_qid": len(pn_qid_pairs),
            "pn_ru_equals_wd_ru_normalized": exact_same_qid,
        },
        "string_agreement_all_matches": None,   # computed in report
        "coverage_by_type": {
            t: {
                "pn_match": sum(1 for r in rows if r["entity_type"] == t and r["paranames_match_type"] != "none"),
                "wd_ru": sum(1 for r in rows if r["entity_type"] == t and r["wikidata_ru"]),
                "n": sum(1 for r in rows if r["entity_type"] == t),
            } for t in sorted({r["entity_type"] for r in rows})
        },
    }
    # cases: mandatory list present in sample?
    MANDATORY = ["Smith", "Smyth", "New York", "London", "George", "Arsenal", "Washington",
                 "Yinchuan", "Red Box", "@ Giants", "National Football League Round 6",
                 "current", "Ha-218", "Fashion Magazine", "Student/Model", "Allsvenskan",
                 "Toronto Maple Leafs", "Cooper-Maserati"]
    px = {r["source_surface"].strip().casefold(): r for r in rows}
    found = {}
    for m in MANDATORY:
        found[m] = "FOUND" if m.casefold() in px else "NOT_FOUND_IN_SAMPLE"
    stats["mandatory_in_sample"] = found
    (HERE / "paranames_eval.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
