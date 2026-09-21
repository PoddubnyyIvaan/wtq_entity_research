"""Experiment 6 - QC metrics comparison (LLM-free, Wikidata as evidence base).

A. Round-trip exact match (diagnostic): does back-translating the RU form
   reproduce the source string?
B. Normalized lexical match: EN label of the linked QID vs source cell value.
C. Entity identity preservation: RU form reverse-linked QID == forward QID.
D. Translation memory consistency: identical surface values identical RU.
E. LLM judge: NOT RUN — no API credentials (recorded obstacle).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Http, jdump, jdumpl, norm_key

WD = "https://www.wikidata.org/w/api.php"


def is_latin(s: str) -> bool:
    return bool(s) and all(ord(ch) < 0x400 for ch in s if ch.isalpha())


def strip_noise(s: str) -> str:
    s = re.sub(r"\((?:[^()]|\([^()]*\))*\)$", "", s).strip()
    s = re.sub(r"[^\w\s\-']", " ", s, flags=re.UNICODE)
    return " ".join(s.split()).casefold()


def norm_unicode(s: str) -> str:
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    return strip_noise(s)


def main():
    root = Path(__file__).resolve().parents[1]
    exp2 = [json.loads(l) for l in (root / "results" / "exp2_wikidata.jsonl").open()]
    http = Http("exp6_batch", min_interval=0.55)

    # --- EN labels for linked QIDs (batched wbgetentities, cached)
    qids = sorted({r["qid"] for r in exp2 if r["qid"]})
    enlab = {}
    for k in range(0, len(qids), 50):
        batch = qids[k:k + 50]
        g = http.get_json(f"{WD}?action=wbgetentities&ids={'|'.join(batch)}&props=labels&languages=en&format=json&origin=*")
        if "__error__" in g:
            continue
        for q, ent in g.get("entities", {}).items():
            lb = (ent.get("labels") or {}).get("en") or {}
            enlab[q] = lb.get("value", "") if isinstance(lb, dict) else ""

    # --- reverse lookup per distinct RU form (dedup; subsample 60 to respect rate limits)
    import random as _random
    _rng = _random.Random(42)
    ru_forms = sorted({r["ru_form"] for r in exp2 if r["ru_form"]})
    if len(ru_forms) > 60:
        ru_forms_sub = set(_rng.sample(ru_forms, 60))
    else:
        ru_forms_sub = set(ru_forms)
    reverse = {}
    for i, ru in enumerate(sorted(ru_forms_sub)):
        if i % 10 == 0:
            print(f"exp6 reverse: {i}/{len(ru_forms_sub)}", flush=True)
        u = (f"{WD}?action=wbsearchentities&search={urllib.parse.quote(ru)}&language=ru"
             f"&format=json&limit=5&type=item&origin=*")
        s = http.get_json(u)
        if "__error__" in s:
            reverse[ru] = ""
            continue
        cands = s.get("search", [])
        reverse[ru] = cands[0]["id"] if cands else ""

    rows = []
    for r in exp2:
        qid = r["qid"]
        ru = r.get("ru_form", "")
        row = {
            "example_id": r["example_id"], "type": r["candidate_type"], "source": r["source"],
            "qid": qid, "ru_form": ru, "ru_source": r.get("ru_source", ""),
            "en_label": enlab.get(qid, ""), "score": r["score"],
        }
        if not ru:
            row.update({"reverse_qid": "", "identity": None, "flags": r["flags"] + ["no_ru_form"]})
        else:
            rq = reverse.get(ru, "")
            row["reverse_qid"] = rq
            row["identity"] = (rq == qid) if rq else None
            flags = list(r["flags"])
            if not rq:
                flags.append("reverse_failed")
            elif rq != qid:
                flags.append("reverse_qid_mismatch")
            row["flags"] = flags
        rows.append(row)

    linked = [r for r in rows if r["qid"]]
    with_en = [r for r in linked if r["en_label"]]
    with_ru = [r for r in rows if r["ru_form"]]
    dup = Counter(norm_unicode(r["source"]) for r in rows)
    ru_by_norm = {}
    for r in with_ru:
        ru_by_norm.setdefault(norm_unicode(r["source"]), set()).add(norm_unicode(r["ru_form"]))
    stats = {
        "n": len(rows),
        "linked_qids": len(linked),
        "A_roundtrip_exact_ru_vs_source": {
            "note": "diagnostic only: RU form rarely equals the EN source string for proper entities",
            "ru_forms": len(with_ru),
            "exact": sum(1 for r in with_ru if norm_key(r["ru_form"]) == norm_key(r["source"])),
        },
        "B_normalized_lexical": {
            "en_label_coverage": sum(1 for r in linked if r["en_label"]) / len(linked),
            "match_rate_among_linked_with_label":
                sum(1 for r in linked if r["en_label"] and norm_unicode(r["en_label"]) == norm_unicode(r["source"]))
                / max(1, sum(1 for r in linked if r["en_label"])),
        },
        "C_entity_identity": {
            "reverse_attempted": len(with_ru),
            "reverse_found": sum(1 for r in with_ru if r["reverse_qid"]),
            "identity_verified": sum(1 for r in with_ru if r["identity"]),
            "identity_verified_rate": sum(1 for r in with_ru if r["identity"]) / max(1, len(with_ru)),
            "reverse_qid_mismatch": sum(1 for r in with_ru if r.get("reverse_qid") and r["reverse_qid"] != r["qid"]),
            "identity_unresolved": sum(1 for r in with_ru if r["identity"] is None),
        },
        "D_tm_consistency": {
            "unique_surface_values": len(dup),
            "repeated_surface_values": sum(1 for v in dup.values() if v > 1),
            "inconsistent_ru_for_same_value": sum(1 for v in ru_by_norm.values() if len(v) > 1),
        },
        "E_llm_judge_status": "NOT RUN: no LLM API credentials available in environment",
    }
    jdump(root / "results" / "exp6_qc_stats.json", stats)
    jdumpl(root / "results" / "exp6_qc.jsonl", rows)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
