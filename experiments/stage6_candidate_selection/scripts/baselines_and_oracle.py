"""Stage 6 — oracle sets + deterministic baselines + feature reranker (clean)."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    s = re.sub(r"\((?:значения|значение)\)", "", s)
    return " ".join(s.split()).casefold().strip()


def strsim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / max(1, len(ta | tb))


def cand_features(s, cands):
    hdr = (s["context"].get("column") or "").casefold()
    out = []
    for c in cands:
        ru = c["ru_form"]
        out.append({
            "lex_sim": strsim(s["surface"], ru),
            "exact": float(norm(s["surface"]) == norm(ru)),
            "cyrillic": float(all(ord(ch) >= 0x400 for ch in (ch for ch in ru if ch.isalpha()))),
            "len": min(len(ru), 40) / 30.0,
            "src_wd_sitelink": float(c["source"] == "wikidata" and c.get("sub") == "sitelink"),
            "src_wd_label": float(c["source"] == "wikidata" and c.get("sub") == "label"),
            "src_wd_alias": float(c.get("sub") == "alias"),
            "src_paranames": float(c["source"] == "paranames"),
            "src_oracle": float(c["source"] == "oracle"),
            "qid_known": float(bool(c.get("qid"))),
            "hdr_team": float(any(k in hdr for k in ("team", "club", "opponent", "winner"))),
            "hdr_geo": float(any(k in hdr for k in ("country", "city", "venue", "location"))),
            "stratum_entity": float(s["entity_type"] not in ("FALSE_POSITIVE", "UNKNOWN")),
        })
    return out


def load_all():
    silver = {r["id"]: r for r in map(json.loads, (HERE / "silver_labels.jsonl").open())}
    sets = {r["id"]: r for r in map(json.loads, (HERE / "candidate_sets.jsonl").open())}
    gold40 = set(json.loads((ROOT / "results" / "gold_llm_translations_40.json").read_text(encoding="utf-8")))
    return silver, sets, gold40


def cmd_oracle():
    silver, sets, _ = load_all()
    out = []
    added = 0
    for sid, s in sets.items():
        sl = silver.get(sid, {})
        cands = [dict(c) for c in s["candidates"]]
        if sl.get("surface_gold") == "available" and sl.get("acceptable_ru_forms"):
            gold_form = sl["acceptable_ru_forms"][0]
            if norm(gold_form) not in {norm(c["ru_form"]) for c in cands}:
                cands.append({"candidate_id": f"candidate_{len(cands) + 1:02d}",
                              "qid": sl.get("gold_entity_qid"),
                              "ru_form": gold_form, "source": "oracle",
                              "source_score": 1.0, "sub": "gold_added"})
                added += 1
        out.append({"id": sid, "candidates": cands})
    with (HERE / "oracle_sets.jsonl").open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("oracle rows:", len(out), "gold added:", added)


def cmd_baselines():
    silver, sets, _ = load_all()
    rows = []
    for sid, s in sets.items():
        if not s["candidates"]:
            continue
        b0 = s["candidates"][0]
        b1 = max(s["candidates"], key=lambda c: (c.get("source_score") or 0))
        for tag, c in [("B0_first", b0), ("B1_score", b1)]:
            rows.append({"id": sid, "method": tag, "selection": c["candidate_id"],
                         "selected_ru": c["ru_form"], "status": "SELECTED"})
    with (HERE / "selection_results.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("deterministic selections:", len(rows))


def cmd_feature_reranker():
    silver, sets, g40 = load_all()
    feats_all, labels_all, meta_all = [], [], []
    for sid, s in sets.items():
        if not s["candidates"]:
            continue
        sl = silver.get(sid, {})
        if sl.get("surface_gold") != "available" or sid in g40:
            continue  # train only on silver surface-gold, never on the human 40
        forms = {norm(f) for f in sl.get("acceptable_ru_forms", [])}
        for f, c in zip(cand_features(s, s["candidates"]), s["candidates"]):
            feats_all.append(f)
            labels_all.append(1 if norm(c["ru_form"]) in forms else 0)
            meta_all.append((sid, c["candidate_id"]))
    keys = list(feats_all[0])
    X = np.array([[f[k] for k in keys] for f in feats_all])
    y = np.array(labels_all)
    clf = GradientBoostingClassifier(random_state=42)
    clf.fit(X, y)
    n_pos = int(y.sum())
    print(f"B2 trained: {len(y)} candidate instances, {n_pos} positive, "
          f"{len(set(m[0] for m in meta_all))} examples")
    byid = defaultdict(list)
    for idx, (sid, cid) in enumerate(meta_all):
        byid[sid].append((cid, float(clf.predict_proba(X[idx:idx + 1])[0][1])))
    # apply to ALL examples with candidates (model trained without g40)
    for sid, s in sets.items():
        if sid in byid or not s["candidates"]:
            continue
        F = cand_features(s, s["candidates"])
        Xa = np.array([[f[k] for k in keys] for f in F])
        for c, prob in zip(s["candidates"], clf.predict_proba(Xa)[:, 1]):
            byid[sid].append((c["candidate_id"], float(prob)))
    rows = []
    for sid, s in sets.items():
        if sid in byid and byid[sid]:
            best_cid, best_p = max(byid[sid], key=lambda t: t[1])
            cands = {c["candidate_id"]: c for c in s["candidates"]}
            rows.append({"id": sid, "method": "B2_gbm", "selection": best_cid,
                         "selected_ru": cands[best_cid]["ru_form"],
                         "status": "SELECTED", "score": round(best_p, 3)})
    with (HERE / "selection_results.jsonl").open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("B2 predictions:", len(rows))
    importances = sorted(zip(keys, clf.feature_importances_.round(3)), key=lambda t: -t[1])
    (HERE / "b2_feature_importance.json").write_text(
        json.dumps({"features": keys, "importance": importance_list(importances)}, ensure_ascii=False, indent=1))


def importance_list(pairs):
    return [{"feature": k, "importance": v} for k, v in importance_sort(pairs)]


def importance_sort(pairs):
    return pairs


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "oracle"
    if cmd == "oracle":
        cmd_oracle()
    elif cmd == "baselines":
        cmd_baselines()
    elif cmd == "feature_reranker":
        cmd_feature_reranker()
