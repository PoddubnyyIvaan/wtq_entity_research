"""Stage 6 - build candidate sets and silver labels from existing artifacts.

Candidate sources (fixed before any ranking): Wikidata (exp3: sitelink/label/
aliases per QID), ParaNames (stage-6 prior results), dedup by normalized RU
form with provenance. NO new retrieval, NO new translation.

Silver labels: identity gold (QID) and surface gold (acceptable RU forms)
tracked separately; confidence levels; ambiguous/unknown kept explicitly.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    s = re.sub(r"\((?:значения|значение)\)", "", s)
    s = re.sub(r"\s+", " ", s.replace("’", "'")).casefold().strip()
    return s


def is_cyr(s):
    return all(ord(c) >= 0x400 for c in s if c.isalpha())


def build_candidate_row(it, e2, e3, pnr):
    qid = e2.get("qid") or None
    cands = []
    cn = 0
    if e3.get("wd_ru_sitelink"):
        cands.append({"candidate_id": f"candidate_{cn + 1:02d}", "qid": qid,
                      "ru_form": e3["wd_ru_sitelink"], "source": "wikidata",
                      "source_score": 0.9, "sub": "sitelink"})
        cn += 1
    if e3.get("wd_ru_label"):
        cands.append({"candidate_id": f"candidate_{cn + 1:02d}", "qid": qid,
                      "ru_form": e3["wd_ru_label"], "source": "wikidata",
                      "source_score": round(float(e2.get("score") or 0), 3), "sub": "label"})
        cn += 1
    for a in (e3.get("wd_ru_aliases") or [])[:2]:
        cands.append({"candidate_id": f"candidate_{cn + 1:02d}", "qid": qid,
                      "ru_form": a, "source": "wikidata",
                      "source_score": 0.5, "sub": "alias"})
        cn += 1
    pnr = pn_by_id.get(it["example_id"], {}) if False else None
    return cands, cn


def main():
    sample = [x for x in map(json.loads, (ROOT / "samples" / "sample200.jsonl").open())]
    exp2 = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp2_wikidata.jsonl").open())}
    exp3 = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp3_sources.jsonl").open())}
    exp6 = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp6_qc.jsonl").open())}
    pn_by_id = {r["id"]: r for r in
                map(json.loads, (ROOT / "experiments" / "paranames" / "paranames_results.jsonl").open())}

    sets_rows, silver_rows = [], []
    for it in sample:
        eid = it["example_id"]
        e2 = exp2.get(eid, {})
        e3 = exp3.get(eid, {})
        qid = e2.get("qid") or None
        cands, cn = [], 0
        if e3.get("wd_ru_sitelink"):
            cands.append({"candidate_id": f"candidate_{cn + 1:02d}", "qid": qid,
                          "ru_form": e3["wd_ru_sitelink"], "source": "wikidata",
                          "source_score": 0.9, "sub": "sitelink"})
            cn += 1
        if e3.get("wd_ru_label"):
            cands.append({"candidate_id": f"candidate_{cn + 1:02d}", "qid": qid,
                          "ru_form": e3["wd_ru_label"], "source": "wikidata",
                          "source_score": round(float(e2.get("score") or 0), 3), "sub": "label"})
            cn += 1
        for a in (e3.get("wd_ru_aliases") or [])[:2]:
            cands.append({"candidate_id": f"candidate_{cn + 1:02d}", "qid": qid,
                          "ru_form": a, "source": "wikidata",
                          "source_score": 0.5, "sub": "alias"})
            cn += 1
        pnr = pn_by_id.get(eid, {})
        for c in (pnr.get("paranames_candidates") or [])[:2]:
            if norm(c["ru"]) in {norm(x["ru_form"]) for x in cands}:
                for x in cands:
                    if norm(x["ru_form"]) == norm(c["ru"]):
                        x.setdefault("also_seen", []).append("paranames")
                continue
            cands.append({"candidate_id": f"candidate_{cn + 1:02d}", "qid": c.get("qid"),
                          "ru_form": c["ru"], "source": "paranames",
                          "source_score": 0.5, "sub": None, "type": c.get("type")})
            cn += 1
        seen, dedup = set(), []
        for c in cands:
            k = norm(c["ru_form"])
            if k in seen:
                for d in dedup:
                    if norm(d["ru_form"]) == k:
                        d.setdefault("also", []).append(c["source"])
                continue
            seen.add(k)
            dedup.append(c)
        sets_rows.append({
            "id": eid, "surface": it["cell_value"], "entity_type": it["candidate_type"],
            "context": {"column": it["column_header"],
                        "row": " | ".join(v for v in it["row_context"].values() if v)[:200],
                        "question": it["question_context"] or None,
                        "page_title": it["table_caption_or_title"] or it["page_title"] or None},
            "candidates": dedup, "n_candidates": len(dedup),
            "sources_present": sorted({c["source"] for c in dedup}),
        })
        # ---- silver label ----
        identity = exp6.get(eid, {}).get("identity")
        flags = e2.get("flags") or []
        ambiguous = ("disambiguation_page" in flags or "low string match" in flags)
        ru = e2.get("ru_form") or ""
        sl = {"id": eid, "source": it["cell_value"], "entity_type": it["candidate_type"],
              "n_candidates": len(dedup),
              "gold_entity_qid": None, "acceptable_ru_forms": [],
              "silver_level": 0, "silver_confidence": 0.0,
              "identity_gold": "unknown", "surface_gold": "unknown",
              "silver_label_source": "none",
              "silver_identity_basis": "", "silver_surface_basis": ""}
        pn_same = [c for c in (pnr.get("paranames_candidates") or []) if c.get("qid") == qid]
        if identity and is_cyr(ru) and "(" not in ru and len(ru) >= 3 and not ambiguous:
            sl.update({"gold_entity_qid": qid, "acceptable_ru_forms": [ru],
                       "silver_level": 1, "silver_confidence": 0.95,
                       "identity_gold": "available", "surface_gold": "available",
                       "silver_label_source": "verified_qid+wd_form",
                       "silver_identity_basis": "exp6 reverse identity==True",
                       "silver_surface_basis": "WD ru form"})
        elif qid and pn_same and not ambiguous and is_cyr(pn_same[0]["ru"]):
            forms = sorted({norm(x) for x in [pn_same[0]["ru"], ru] if ru})
            sl.update({"gold_entity_qid": qid,
                       "acceptable_ru_forms": [pn_same[0]["ru"]] + ([ru] if ru else []),
                       "silver_level": 2, "silver_confidence": 0.8,
                       "identity_gold": "available",
                       "surface_gold": "available" if is_cyr(pn_same[0]["ru"]) else "unknown",
                       "silver_label_source": "wd+paranames_same_qid",
                       "silver_identity_basis": "qid from exp2, same-qid PN support",
                       "silver_surface_basis": "PN ru form"})
        elif identity and not ambiguous:
            sl.update({"gold_entity_qid": qid, "silver_level": 3,
                       "silver_confidence": 0.6, "identity_gold": "available",
                       "surface_gold": "unknown",
                       "silver_label_source": "verified_qid_no_form",
                       "silver_identity_basis": "exp6 identity==True, WD/PN RU form missing",
                       "silver_surface_basis": ""})
        elif identity is False and not ambiguous:
            # known wrong QID -> surface gold = none available; abstention is right
            sl.update({"silver_level": 4, "silver_confidence": 0.6,
                       "identity_gold": "available", "surface_gold": "unknown",
                       "silver_label_source": "verified_qid_mismatch",
                       "silver_identity_basis": "exp6 reverse found different QID",
                       "gold_entity_qid": None})
        elif not identity:
            # unresolved: ambiguous or no reverse
            if ambiguous and not identity:
                sl.update({"silver_level": 0, "silver_confidence": 0.3,
                           "identity_gold": "ambiguous", "surface_gold": "unknown",
                           "silver_label_source": "ambiguous_resolver"})
            else:
                sl.update({"silver_level": 0, "silver_confidence": 0.2,
                           "identity_gold": "unknown", "surface_gold": "unknown",
                           "silver_label_source": "no_resolver_evidence"})
        silver_rows.append(sl)
    with (HERE / "candidate_sets.jsonl").open("w", encoding="utf-8") as f:
        for r in sets_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (HERE / "silver_labels.jsonl").open("w", encoding="utf-8") as f:
        for r in silver_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    st = {
        "n": len(sets_rows),
        "candidates_dist": dict(Counter(r["n_candidates"] for r in sets_rows)),
        "silver_levels": dict(Counter(r["silver_level"] for r in silver_rows)),
        "identity_gold": dict(Counter(r["identity_gold"] for r in silver_rows)),
        "surface_gold": dict(Counter(r["surface_gold"] for r in silver_rows)),
        "sources": Counter(",".join(r["sources_present"]) for r in sets_rows),
    }
    (HERE / "build_stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: st[k] for k in ("n", "candidates_dist", "silver_levels", "identity_gold", "surface_gold")}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
