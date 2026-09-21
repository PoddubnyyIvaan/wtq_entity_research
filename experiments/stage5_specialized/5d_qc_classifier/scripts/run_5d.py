"""Experiment 5D - light QC classifier vs rule-based QC and LLM-judge.

Features from existing artifacts for the 40 manually labeled cases:
identity_verified, resolver score, string similarity, P31/header match,
ru_source, dictionary agreement count, paranames match, LLM confidence.
Target: manual needs_review from gold_llm_translations_40.json.
Leave-one-out cross-validation (n=40, proof-of-concept).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.model_selection import LeaveOneOut

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]

MAX = lambda x, y: max(1, len(x)) if False else y  # noqa


def str_sim(a, b):
    if not a or not b:
        return 0.0
    a, b = a.strip().casefold(), b.strip().casefold()
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / max(1, len(ta | tb))


def main():
    sample = {x["example_id"]: x for x in map(json.loads, (ROOT / "samples" / "sample200.jsonl").open())}
    gold = json.loads((ROOT / "results" / "gold_llm_translations_40.json").read_text(encoding="utf-8"))
    exp2 = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp2_wikidata.jsonl").open())}
    exp6 = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp6_qc.jsonl").open())}
    exp1 = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp1_llm_context.jsonl").open())
            if r["mode"] == "D"}
    pn = {r["id"]: r for r in map(json.loads, (ROOT / "experiments" / "paranames" / "paranames_results.jsonl").open())}
    dicts = {}
    for d, p in [("wikidict", "wikidict/results.jsonl"), ("wiktionary", "wiktionary/results.jsonl"),
                 ("openrussian", "openrussian/results.jsonl"),
                 ("statistical_full", "statistical/results_full.jsonl"),
                 ("statistical_filtered", "statistical/results_filtered.jsonl")]:
        for r in map(json.loads, (ROOT / "experiments" / "dictionaries" / p).open()):
            dicts.setdefault(r["id"], {}).setdefault(d, set()).update(
                c["ru"] for c in r["candidates"])

    ids = sorted(gold)
    feats, ys = [], []
    for eid in ids:
        it = sample[eid]
        e2 = exp2.get(eid, {})
        e1 = exp1.get(eid, {})
        q6 = exp6.get(eid, {})
        hdr = it["column_header"].casefold()
        # features
        f = {}
        f["identity_verified"] = float(bool(q6.get("identity")))
        f["reverse_mismatch"] = float(bool(q6.get("reverse_qid")) and q6.get("identity") is False)
        f["resolver_score"] = float(e2.get("score") or 0)
        f["lex_match_en"] = float(stratum_string_sim(e2.get("en_label", ""), it["cell_value"]))
        f["ru_cyrillic"] = float(all(ord(c) >= 0x400 for c in (e2.get("ru_form") or "x") if c.isalpha()))
        f["ru_source_sitelink"] = float(e2.get("ru_source") == "ru_sitelink")
        f["header_keyword_team"] = float(any(k in hdr for k in ("team", "club", "opponent", "winner")))
        f["header_keyword_country"] = float(any(k in hdr for k in ("country", "nation", "city")))
        f["pn_match"] = float(bool(pn.get(eid, {}).get("paranames_candidates")))
        pn_types = {c.get("type") for c in pn.get(eid, {}).get("paranames_candidates", [])}
        expected = {"PERSON", "SURNAME"} if it["candidate_type"] in ("PERSON", "SURNAME") else \
            {"LOCATION"} if it["candidate_type"] == "LOCATION" else \
            {"ORG", "ORGANIZATION", "SPORTS_TEAM"} if it["candidate_type"] in ("ORGANIZATION", "SPORTS_TEAM") else set()
        f["pn_type_matches"] = float(bool(pn_types & expected))
        # dictionary agreement count: number of dicts sharing any candidate form
        dd = dicts.get(eid, {})
        forms = {}
        for d, cands in dd.items():
            for c in cands:
                forms.setdefault(c, set()).add(d)
        f["dict_agreement_max"] = max((len(v) for v in forms.values()), default=0)
        f["llm_confidence"] = float(e1.get("confidence") or 0)
        f["llm_conf_sq"] = f["llm_confidence"] ** 2
        f["status_flag_ambiguous"] = float("multiple plausible QIDs" in (e2.get("flags") or []))
        f["is_entity_stratum"] = float(it["candidate_type"] not in ("FALSE_POSITIVE", "UNKNOWN"))
        feats.append(f)
        ys.append(1 if gold[eid]["needs_review"] else 0)

    keys = list(feats[0])
    X = np.array([[r[k] for k in keys] for r in feats])
    y = np.array(ys)
    print("features:", keys, "| pos:", y.sum(), "/", len(y))

    results = {}
    for name, mk in [("logreg", lambda: LogisticRegression(max_iter=1000)),
                     ("gradboost", lambda: GradientBoostingClassifier(random_state=42))]:
        y_pred, y_prob = [], []
        coefs = []
        for i in range(len(y)):
            idx = [j for j in range(len(y)) if j != i]
            clf = mk()
            clf.fit(X[idx], y[idx])
            y_pred.append(int(clf.predict(X[i:i + 1])[0]))
            y_prob.append(float(clf.predict_proba(X[i:i + 1])[0][1]))
            if name == "logreg":
                coefs.append(clf.coef_[0])
        acc = accuracy_score(y, y_pred)
        f1 = f1_score(y, y_pred)
        results[name] = {"loo_accuracy": round(acc, 3), "loo_f1": round(f1, 3),
                         "confusion": confusion_matrix(y, y_pred).tolist(),
                         "pred_review_rate": float(np.mean(y_pred))}
        if name == "logreg":
            results["feature_importance_logreg"] = sorted(
                zip(keys, np.mean(coefs, axis=0).round(2).tolist()), key=lambda t: -abs(t[1]))

    # baselines on the same 40, same framing (predict needs_review)
    stat_rows = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp6b_status.jsonl").open())}
    rule_pred = [1 if stat_rows[i]["status"] in ("SUSPICIOUS", "AMBIGUOUS") else 0 for i in ids]
    results["baseline_rule"] = {"loo_accuracy": round(accuracy_score(y, rule_pred), 3),
                                "pred_review_rate": float(np.mean(rule_pred))}
    J = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp6e_llm_judge.jsonl").open())}
    judge_pred = [1 if J[i]["judge"].get("needs_review") else 0 for i in ids]
    results["baseline_llm_judge_3b"] = {"agreement": round(accuracy_score(y, judge_pred), 3),
                                        "pred_review_rate": float(np.mean(judge_pred))}
    (HERE / "results" / "qc_classifier_results.json").write_text(
        json.dumps({"features": keys, "target": "manual needs_review (40)",
                    "results": results}, ensure_ascii=False, indent=1))
    print(json.dumps(results, ensure_ascii=False, indent=1)[:2500])


def stratum_string_sim(a, b):
    if not a or not b:
        return 0.0
    a, b = a.strip().casefold(), b.strip().casefold()
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / max(1, len(ta | tb))


if __name__ == "__main__":
    main()
