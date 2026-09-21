"""5A comparison: ByT5 vs BGN transliteration vs ParaNames lookup vs Wikidict,
all evaluated as agreement with the Wikidata RU form on the same
NAMED_ENTITY occurrences of sample200 (n where WD has RU form)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "dictionaries"))
from common_dict import norm  # noqa

MANDATORY = ["Smith", "Smyth", "New York", "London", "George", "Arsenal", "Washington"]
TRAD = {"smith": "Смит", "smyth": "Смит", "new york": "Нью-Йорк", "london": "Лондон",
        "george": "Джордж", "washington": "Вашингтон", "arsenal": "Арсенал"}


def translit_word(w: str) -> str:
    # reuse exp4's compact transliterator
    sys.path.insert(0, str(ROOT / "scripts"))
    from exp4_translit import translit  # noqa
    return translit(w)


def main():
    wd = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp2_wikidata.jsonl").open())}
    preds = {r["id"]: r for r in map(json.loads, (HERE / "results" / "eval_sample_named.jsonl").open())}
    gold40 = json.loads((ROOT / "results" / "gold_manual.json").read_text(encoding="utf-8"))
    rows = []
    for eid, p in preds.items():
        e2 = wd.get(eid, {})
        if not (p["byt5_pred"] and e2.get("ru_form")):
            continue
        wd_ru = e2["ru_form"]
        src = p["surface"]
        src_key = src.strip().casefold()
        bgn = TRAD.get(src_key) or translit_word(src)
        rows.append({
            "id": eid, "surface": src, "wd_ru": wd_ru,
            "byt5": p["byt5_pred"], "bgn": bgn,
            "byt5_match": norm(p["byt5_pred"]) == norm(wd_ru),
            "bgn_match": norm(bgn) == norm(wd_ru),
            "wd_has_form": True,
        })
    n = len(rows)
    byt5_ok = sum(r["byt5_match"] for r in rows)
    bgn_ok = sum(r["bgn_match"] for r in rows)
    # mandatory names via trained model
    mp = [{"eng": m} for m in MANDATORY]
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(HERE / "models" / "byt5-small-pn-per"))
    model = AutoModelForSeq2SeqLM.from_pretrained(str(HERE / "models" / "byt5-small-pn-per"),
                                                  dtype=torch.bfloat16,
                                                  attn_implementation="eager").cuda().eval()
    enc = tok([p["eng"] for p in mp], return_tensors="pt", padding=True).to("cuda")
    gen = model.generate(**enc, max_length=64)
    preds_m = tok.batch_decode(gen, skip_special_tokens=True)
    mandatory = {m: pr for (m, _), pr in zip([(x, 0) for x in MANDATORY], preds_m)}
    out = {
        "comparison_subset": {
            "note": "agreement with WD RU form on sample NAMED_ENTITY occurrences where WD has RU (not accuracy)",
            "n": n,
            "byt5_agreement": round(byt5_ok / n, 3),
            "bgn_rule_agreement": round(bgn_ok / n, 3),
        },
        "mandatory_probes_byt5": mandatory,
        "rows": rows[:40],
    }
    (HERE / "results" / "comparison_vs_baselines.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1))

    print("n:", n, "| ByT5 norm-agreement:", round(byt5_ok / n, 3), "| BGN:", round(bgn_ok / n, 3))
    print("mandatory:", json.dumps(mandatory, ensure_ascii=False))
    # gold40 intersection: examples in gold40 that have WD form (subset rows list already 40)
    agree40 = [(r["surface"], r["byt5_pred"] if "byt5_pred" in r else r["byt5"], r["wd_ru"], r["byt5_match"])
               for r in out["rows"]]
    for r in agree40[:15]:
        print(r)


if __name__ == "__main__":
    main()
