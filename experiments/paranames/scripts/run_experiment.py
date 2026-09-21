"""ParaNames experiment — Variant A (ParaNames only) on the 200 WTQ sample.

Merges: existing sample200.jsonl, exp2 (Wikidata rupform/qid), exp3 (wiki
langlinks), exp1 mode D (qwen translation). No blind replacement: every match
keeps candidate list and metadata; single-candidate match is 'selected'.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]              # wtq_entity_research
sys.path.insert(0, str(ROOT / "scripts"))

PN_INDEX = HERE / "cache" / "paranames_en_ru.jsonl"
OUT = HERE / "paranames_results.jsonl"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    s = s.replace("’", "'").replace("–", "-").replace("—", "-")
    s = re.sub(r"[@#]", " ", s).strip(" @-")
    return " ".join(s.split()).casefold().strip()


def load_index():
    idx = {}
    with PN_INDEX.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            k = o["key"]
            if k not in idx:
                idx[k] = o["cands"]
            else:
                idx[k].extend(o["cands"])
    return idx


def main():
    sample = [json.loads(l) for l in (ROOT / "samples" / "sample200.jsonl").open()]
    exp2 = {r["example_id"]: r for r in
            (json.loads(l) for l in (ROOT / "results" / "exp2_wikidata.jsonl").open())}
    exp3 = {r["example_id"]: r for r in
            (json.loads(l) for l in (ROOT / "results" / "exp3_sources.jsonl").open())}
    exp1 = {}
    for l in (ROOT / "results" / "exp1_llm_context.jsonl").open():
        r = json.loads(l)
        if r["mode"] == "D":
            exp1[r["example_id"]] = r
    idx = load_index()
    global PN_BY_QID
    PN_BY_QID = json.loads((HERE / "cache" / "paranames_by_qid.json").read_text(encoding="utf-8"))
    print("index keys:", len(idx), "qid entries:", len(PN_BY_QID), flush=True)

    rows = []
    for it in sample:
        eid = it["example_id"]
        cell = it["cell_value"]
        e2 = exp2.get(eid, {})
        e3 = exp3.get(eid, {})
        e1 = exp1.get(eid, {})
        key = norm(cell)
        cands = idx.get(key, [])
        # also try cleaned variants: lowercase w/o annotations
        variants = [key]
        alt = norm(re.sub(r"\((?:[^()]|\([^()]*\))*\)", "", cell))
        if alt and alt != key:
            variants = idx.get(alt, [])
            if variants and not cands:
                cands = variants
        match_type = ("none" if not cands else "single" if len(cands) == 1 else "multiple")
        pn_source = "en_key" if cands else ""
        # fallback: QID-based lookup (identity-preserving path via exp2 qid)
        if not cands and e2.get("qid"):
            q = e2["qid"]
            qicands = PN_BY_QID.get(q, [])
            if qicands:
                cands = qicands
                match_type = ("single" if len(cands) == 1 else "multiple")
                pn_source = "qid"
        # track which path produced the match
        pn_lookup = pn_source or "none"
        type_map = {ew: {"PER": "PERSON", "LOC": "LOCATION", "ORG": "ORGANIZATION"}
                    for ew in []}
        pn_types = sorted({c["type"] for c in cands})
        selected = None
        if match_type == "single":
            selected = cands[0]["ru"]
        decision = {"none": "NO_MATCH", "single": "ACCEPT", "multiple": "REVIEW"}[match_type]
        if cands and len(cands) > 1:
            decision = "REVIEW"
        rows.append({
            "id": eid,
            "source_surface": cell,
            "entity_type": it["candidate_type"],
            "qid": e2.get("qid") or None,
            "context": {
                "column": it["column_header"],
                "row": " | ".join(v for v in it["row_context"].values() if v),
                "question": it["question_context"] or None,
            },
            "paranames_candidates": cands[:12],
            "paranames_match_type": match_type,
            "paranames_selected": selected,
            "paranames_types": pn_types,
            "paranames_lookup": pn_lookup,
            "wikidata_ru": e2.get("ru_form") or None,
            "wikipedia_ru": e3.get("wiki_langlinks_ru") or None,
            "qwen_selected": e1.get("translation") or None,
            "final_candidate": None,
            "decision": decision,
            "reason": "",
        })
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    st = {
        "n": len(rows),
        "match_type": dict(Counter(r["paranames_match_type"] for r in rows)),
        "decision": dict(Counter(r["decision"] for r in rows)),
    }
    (HERE / "results_paranames_stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
    print(json.dumps(st, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
