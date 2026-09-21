"""Experiment 6b - QC decision rules (sec.19) applied to the evaluation sample.

Combines exp0/2/3/4/6 evidence into per-item statuses:
VERIFIED / ACCEPTABLE_WITHOUT_ENTITY_ID / AMBIGUOUS / SUSPICIOUS /
INCORRECT / UNRESOLVED  (plus NA_ENTITY_QC for FALSE_POSITIVE cells).

Rules are experimental: compared against a small human-verified subsample
(human annotations in results/gold_manual.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import jdump, jdumpl, norm_key, jload

ALL_CYR = lambda s: s and all(ord(c) >= 0x400 for c in s if c.isalpha())


def is_latin(s: str) -> bool:
    return bool(s) and all(ord(ch) < 0x400 for ch in s if ch.isalpha())


def main():
    root = Path(__file__).resolve().parents[1]
    sample = {x["example_id"]: x for x in
              (json.loads(l) for l in (root / "samples" / "sample200.jsonl").open())}
    exp2 = [json.loads(l) for l in (root / "results" / "exp2_wikidata.jsonl").open()]
    exp6 = {r["example_id"]: r for r in
            (json.loads(l) for l in (root / "results" / "exp6_qc.jsonl").open())}
    gold = jload(root / "results" / "gold_manual.json", {})

    rows = []
    for r in exp2:
        it = sample[r["example_id"]]
        q6 = exp6.get(r["example_id"], {})
        flags = set(r["flags"]) | set(q6.get("flags", []))
        fp = r["candidate_type"] == "FALSE_POSITIVE"
        cyr_clean = ALL_CYR(r["ru_form"]) and len(r["ru_form"]) >= 3 \
            and "(" not in r["ru_form"] and "значения" not in r["ru_form"]
        status = None
        if fp:
            status = "NA_ENTITY_QC"
        elif not r["qid"]:
            status = "UNRESOLVED"
        elif q6.get("identity"):
            status = "VERIFIED"
        elif "multiple plausible QIDs" in flags or "disambiguation_page" in flags:
            status = "AMBIGUOUS"
        elif "low string match" in flags:
            status = "SUSPICIOUS"
        elif q6.get("reverse_qid") and q6.get("identity") is False:  # reverse found different qid
            status = "SUSPICIOUS"
        elif cyr_clean and "low string match" not in flags:
            status = "ACCEPTABLE_WITHOUT_ENTITY_ID"
        else:
            status = "UNRESOLVED"
        rows.append({
            "example_id": r["example_id"], "type": r["candidate_type"],
            "source": r["source"], "ru_form": r["ru_form"], "qid": r["qid"],
            "status": status, "flags": sorted(flags),
        })
    from collections import Counter
    stats = {
        "decision_rule_status_distribution": dict(Counter(r["status"] for r in rows)),
        "note": "LLM-judge-based ACCEPT branch not simulated (no LLM access); manual-review rate is the share not VERIFIED/ACCEPTABLE",
        "manual_review_rate": sum(1 for r in rows if r["status"] in ("SUSPICIOUS", "AMBIGUOUS")) / len(rows),
        "unresolved_rate": sum(1 for r in rows if r["status"] == "UNRESOLVED") / len(rows),
        "verified_or_acceptable_rate": sum(1 for r in rows if r["status"] in ("VERIFIED", "ACCEPTABLE_WITHOUT_ENTITY_ID")) / len(rows),
    }
    # agreement with human labels where available
    if gold:
        known = [r for r in rows if r["example_id"] in gold]
        strict = sum(1 for r in known if gold[r["example_id"]]["status_ok"] == "yes")
        partial = sum(1 for r in known if gold[r["example_id"]]["status_ok"] == "partial")
        wrong = sum(1 for r in known if gold[r["example_id"]]["status_ok"] == "no")
        stats["gold_checked"] = len(known)
        stats["rule_human_agreement_strict"] = strict
        stats["rule_human_agreement_partial"] = partial
        stats["rule_human_agreement_wrong"] = wrong
    jdump(root / "results" / "exp6b_status_stats.json", stats)
    jdumpl(root / "results" / "exp6b_status.jsonl", rows)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
