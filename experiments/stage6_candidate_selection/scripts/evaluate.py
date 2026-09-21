"""Stage 6 — evaluation (FINAL). Writes tables/*.csv + metrics.json.

Framings kept separate: human-40 (A), silver (B), oracle/shuffled (C).
Human-40 ground truth: stage-1 manual subset (single rater), used only here.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
T = HERE / "tables"
T.mkdir(exist_ok=True)

# --- single-rater manual verdicts for the human-40 (from stage-1 subset) ---
MANUAL_ACCEPTABLE = {
    "e029": ["Чемпионат Швеции по футболу"],
    "e082": ["Андретти, Майкл", "Майкл Андретти"],
    "e180": ["Кейдж, Майкл", "Майкл Кейдж"],
    "e046": ["Северн, Дэн", "Дэн Северн"],
    "e026": ["Сиддикуи, Ислахуддин", "Ислахуддин Сиддикуи"],
    "e122": ["BP", "«Би-Пи»", "БП"],
    "e169": ["BMW M1", "БМВ М1"],
}
MANUAL_HARMFUL_FORMS = {
    "e121": ["Буквенно-цифровое обозначение аккорда"],
    "e095": ["BMW M", "БМВ М"],
    "e007": ["Национальная футбольная лига"],
    "e119": ["Национальная футбольная лига"],
    "e034": ["Гиганты"],
    "e131": ["значение отсутствует (личное имя)", "неприменимый", "недоступный"],
    "e073": ["Берлинские кварталы эпохи модернизма"],
    "e114": ["течение"],
    "e129": ["14 ноября"],
    "e002": ["Красная коробка"],
    "e033": ["Йинчжоу", "Йinchuan"],
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    s = re.sub(r"\((?:значения|значение)\)", "", s)
    return " ".join(s.split()).casefold().strip()


def load():
    sets = {r["id"]: r for r in map(json.loads, (HERE / "candidate_sets.jsonl").open())}
    silver = {r["id"]: r for r in map(json.loads, (HERE / "silver_labels.jsonl").open())}
    return sets, silver


def llm_groups():
    g = {}
    for m, short in (("qwen7b", "Qwen7B"), ("qwen3b", "Qwen3B")):
        d = HERE / "raw" / m
        if not d.exists():
            continue
        for f in d.glob("sel_*.jsonl"):
            parts = f.stem.split("_")
            tag, mode = parts[1], parts[2]
            g[(short, tag, mode)] = {r["id"]: r for r in map(json.loads, f.open())}
    return g


def verdict(sid, row, sr, sets):
    """CORRECT / WRONG / FALSE_POSITIVE / CORRECT_ABSTAIN / MISSED / INVALID / SKIP."""
    exists_surface = sr["surface_gold"] == "available"
    exists_identity = sr["identity_gold"] == "available" and sr.get("gold_entity_qid")
    st = row["status"]
    if st == "NO_MATCH":
        return "MISSED" if (exists_surface or exists_identity) else "ABSTAIN"
    if st in ("INVALID_SELECTION", "PARSE_FAIL"):
        return "INVALID"
    ru = row.get("selected_ru") or ""
    gold_forms = {norm(f) for f in sr.get("acceptable_ru_forms", [])}
    cands = {c["candidate_id"]: c for c in sets[sid]["candidates"]}
    sel_qid = cands.get(row["selection"], {}).get("qid")
    ok_identity = bool(sr.get("gold_entity_qid") and sel_qid == sr["gold_entity_qid"])
    if exists_surface:
        return "CORRECT" if (norm(ru) in gold_forms or ok_identity) else "WRONG"
    if exists_identity:
        return "CORRECT" if ok_identity else "FALSE_POSITIVE"
    if sid in MANUAL_ACCEPTABLE:
        if norm(ru) in {norm(f) for f in MANUAL_ACCEPTABLE[sid]}:
            return "CORRECT"
    if sid in MANUAL_HARMFUL_FORMS and norm(ru) in {norm(f) for f in MANUAL_HARMFUL_FORMS[sid]}:
        return "WRONG"
    return "CORRECT"


def agg(vs):
    c = Counter(vs.values())
    labeled = c["CORRECT"] + c["WRONG"] + c["FALSE_POSITIVE"]
    return {
        "attempted": sum(c.values()),
        "correct": c["CORRECT"],
        "wrong": c["WRONG"],
        "false_positive": c["FALSE_POSITIVE"],
        "correct_abstain": c["ABSTAIN"],
        "missed_candidate": c["MISSED"],
        "invalid": c["INVALID"],
        "selection_agreement": round(c["CORRECT"] / max(1, labeled), 3),
        "no_match_rate": round((c["MISSED"] + c["ABSTAIN"]) / max(1, sum(c.values())), 3),
        "no_match_when_candidate_exists": c["MISSED"],
        "harmful_substitution": c["WRONG"],
    }


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    sets, silver = load()
    groups = llm_groups()
    gold40 = json.loads((ROOT / "results" / "gold_llm_translations_40.json").read_text(encoding="utf-8"))

    # ---------------- retrieval ----------------
    surface_ids = [i for i, r in silver.items() if r["surface_gold"] == "available"]
    identity_ids = [i for i, r in silver.items() if r["identity_gold"] == "available"]
    rec = {k: {"identity": 0, "surface": 0} for k in (1, 3, 5)}
    for i in surface_ids:
        forms = {norm(f) for f in silver[i]["acceptable_ru_forms"]}
        for k in (1, 3, 5):
            if any(norm(c["ru_form"]) in forms for c in sets[i]["candidates"][:k]):
                rec[k]["surface"] += 1
    for i in identity_ids:
        qid = silver[i]["gold_entity_qid"]
        for k in (1, 3, 5):
            if any(c.get("qid") == qid for c in sets[i]["candidates"][:k]):
                rec[k]["identity"] += 1
    retrieval = {
        "n": len(sets),
        "candidate_coverage": round(sum(1 for s in sets.values() if s["candidates"]) / len(sets), 3),
        "surface_gold_n": len(surface_ids),
        "identity_gold_n": len(identity_ids),
        "identity_recall@1": rec[1]["identity"],
        "identity_recall@3": rec[3]["identity"],
        "identity_recall@5": rec[5]["identity"],
        "surface_recall@1": rec[1]["surface"],
        "surface_recall@3": rec[3]["surface"],
        "surface_recall@5": rec[5]["surface"],
    }
    write_csv(T / "retrieval.csv", ["metric", "value"], [[k, v] for k, v in retrieval.items()])

    # ---------------- methods ----------------
    det = defaultdict(dict)
    for r in map(json.loads, (HERE / "selection_results.jsonl").open()):
        det[r["method"]][r["id"]] = r

    methods = [
        ("Resolver_B0", det.get("B0_first", {}), "selection"),
        ("Feature_reranker_B2", det.get("B2_gbm", {}), "selection"),
        ("Qwen3B", groups.get(("Qwen3B", "main", "D"), {}), "selection"),
        ("Qwen7B", groups.get(("Qwen7B", "main", "D"), {}), "selection"),
        ("ORACLE_Qwen3B", groups.get(("Qwen3B", "oracle", "D"), {}), "oracle"),
        ("ORACLE_Qwen7B", groups.get(("Qwen7B", "oracle", "D"), {}), "oracle"),
        ("SHUFFLED_Qwen3B", groups.get(("Qwen3B", "shuffled", "D"), {}), "shuffled"),
        ("SHUFFLED_Qwen7B", groups.get(("Qwen7B", "shuffled", "D"), {}), "shuffled"),
    ]

    selection, oracle_out, shuffled_out = {}, {}, {}
    ablation = []
    human40 = {}

    for name, picks, slot in methods:
        vs = {sid: verdict(sid, row, silver[sid], sets) for sid, row in picks.items() if sid in silver}
        a = agg(vs)
        a["method"] = name
        {"selection": selection, "oracle": oracle_out, "shuffled": shuffled_out}[slot][name] = a
        # human-40 counts
        h = Counter()
        for sid in gold40:
            v = vs.get(sid)
            if v is None:
                continue
            if v == "MISSED":
                h["no_match_when_candidate_exists"] += 1
            elif v == "ABSTAIN":
                h["abstain"] += 1
            elif v == "CORRECT":
                h["selection_correct"] += 1
            elif v in ("WRONG", "FALSE_POSITIVE"):
                h["selection_wrong"] += 1
            elif v == "INVALID":
                h["invalid"] += 1
        human40[name] = dict(h)

    # ---------------- context ablation ----------------
    for ms in ("Qwen7B", "Qwen3B"):
        for mode in ("A", "B", "C", "D", "E"):
            per = groups.get((ms, "abl7b", mode)) or groups.get((ms, "abl3b", mode))
            if per is None and mode == "D":
                per = groups.get((ms, "main", "D"))
            if not per:
                continue
            vs = {sid: verdict(sid, row, silver[sid], sets) for sid, row in per.items()}
            ablation.append({"model": ms, "mode": mode, **agg(vs)})
    write_csv(T / "context_ablation.csv",
              ["model", "mode", "attempted", "correct", "wrong", "false_positive",
               "correct_abstain", "missed_candidate", "invalid",
               "selection_agreement", "no_match_rate"],
              [[a["model"], a["mode"]] + [a[k] for k in ("attempted", "correct", "wrong",
                                                         "false_positive", "correct_abstain",
                                                         "missed_candidate", "invalid",
                                                         "selection_agreement", "no_match_rate")]
               for a in ablation])

    write_csv(T / "selection.csv",
              ["method", "attempted", "correct", "wrong", "false_positive",
               "correct_abstain", "missed_candidate", "invalid",
               "selection_agreement", "no_match_rate"],
              [[n2] + [v[k] for k in ("attempted", "correct", "wrong", "false_positive",
                                      "correct_abstain", "missed_candidate", "invalid",
                                      "selection_agreement", "no_match_rate")]
               for n2, v in selection.items()])

    write_csv(T / "oracle.csv",
              ["method", "attempted", "correct", "wrong", "false_positive",
               "correct_abstain", "missed_candidate", "invalid",
               "selection_agreement", "no_match_rate"],
              [[n2] + [v[k] for k in ("attempted", "correct", "wrong", "false_positive",
                                      "correct_abstain", "missed_candidate", "invalid",
                                      "selection_agreement", "no_match_rate")]
               for n2, v in oracle_out.items()])

    # ---------------- by stratum (mode D) ----------------
    strata_rows = []
    for name in ("Resolver_B0", "Qwen7B", "Qwen3B"):
        picks = next((p for n2, p, _ in methods if n2 == name), {})
        by = defaultdict(Counter)
        for sid, row in picks.items():
            v = verdict(sid, row, silver[sid], sets)
            by[silver[sid]["entity_type"]][v] += 1
        for t, c in by.items():
            strata_rows.append([name, t, c["CORRECT"], c["WRONG"], c["FALSE_POSITIVE"],
                                c["MISSED"], c["ABSTAIN"], c["INVALID"]])
    write_csv(T / "by_stratum.csv",
              ["method", "stratum", "correct", "wrong", "false_positive",
               "missed", "correct_abstain", "invalid"], strata_rows)

    # ---------------- safety ----------------
    safety = {
        "note": ("free-generation counts from stage-2/stage-5 manual 40 (single rater); "
                 "stage6 = harmful candidates picked on the same 40"),
        "free_generation_qwen3b_n40": 12,
        "free_generation_qwen7b_n40": 5,
        "candidate_selection_qwen3b_n40_harmful": human40.get("Qwen3B", {}).get("selection_wrong", 0),
        "candidate_selection_qwen7b_n40_harmful": human40.get("Qwen7B", {}).get("selection_wrong", 0),
        "candidate_selection_qwen7b_n40_correct": human40.get("Qwen7B", {}).get("selection_correct", 0),
    }
    write_csv(T / "safety.csv", ["method", "n", "harmful"],
              [["free_generation_qwen3b", 40, 12],
               ["free_generation_qwen7b", 40, 5],
               ["candidate_selection_qwen3b", 40, human40.get("Qwen3B", {}).get("selection_wrong", 0)],
               ["candidate_selection_qwen7b", 40, human40.get("Qwen7B", {}).get("selection_wrong", 0)]])

    metrics = {"retrieval": retrieval, "selection": selection, "oracle": oracle_out,
               "shuffled": shuffled_out, "ablation": ablation, "safety": safety,
               "human40": human40}
    (HERE / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1))
    print(json.dumps(retrieval, ensure_ascii=False, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in selection.items()},
                     ensure_ascii=False, indent=1)[:1200])


if __name__ == "__main__":
    main()
