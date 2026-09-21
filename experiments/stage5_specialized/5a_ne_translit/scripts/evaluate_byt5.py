"""Evaluate 5A ByT5 model: greedy decode on test split / sample entities /
mandatory names; normalized + exact match rates. Compares with baselines.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

import torch  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
os.environ.setdefault("HF_HOME", str(HERE.parent / ".cache" / "hf"))
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: E402

MODEL_DIR = HERE / "models" / "byt5-small-pn-per"


def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", "".join(c for c in s if not unicodedata.combining(c)))
    s = s.replace("’", "'").replace("–", "-")
    return " ".join(s.split()).casefold().strip()


def main():
    split = json.loads((HERE / "results" / "pn_per_split.json").read_text(encoding="utf-8"))
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSeq2SeqLM.from_pretrained(str(MODEL_DIR), dtype=torch.bfloat16, attn_implementation="eager").cuda().eval()

    def batch_decode(pairs, bs=64):
        outs = []
        lat = []
        for i in range(0, len(pairs), bs):
            chunk = pairs[i:i + bs]
            t0 = time.time()
            enc = tok([p["eng"] for p in chunk], return_tensors="pt", padding=True,
                      truncation=True, max_length=64).to("cuda")
            gen = model.generate(**enc, max_length=64, num_beams=1)
            outs.extend(tok.batch_decode(gen, skip_special_tokens=True))
            lat.append((time.time() - t0) / len(chunk))
        return outs, lat

    rows = {}
    for name in ("test", "dev"):
        pairs = split[name]
        preds, lat = batch_decode(pairs)
        exact = sum(1 for p, pr in zip(pairs, preds) if p["ru"].strip() == pr.strip())
        normalized = sum(1 for p, pr in zip(pairs, preds) if norm(p["ru"]) == norm(pr))
        rows = [{"eng": p["eng"], "gold": p["ru"], "pred": pr, "qid": p["qid"]}
                for p, pr in zip(pairs, preds)]
        with (HERE / "results" / f"eval_{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        res = {"n": len(pairs), "exact": exact, "exact_rate": round(exact / len(pairs), 4),
               "normalized_match_rate": round(normalized / len(pairs), 3),
               "mean_latency_s": round(statistics.mean(lat), 4)}
        print(name, json.dumps(res), flush=True)
        rows_out = res
        if name == "test":
            json.dump(res, open(HERE / "results" / "eval_test_stats.json", "w"))

    # sample200 NAMED_ENTITY subset
    sample = [x for x in map(json.loads, (ROOT / "samples" / "sample200.jsonl").open())
              if x["candidate_type"] in ("PERSON", "SURNAME", "LOCATION", "ORGANIZATION",
                                         "SPORTS_TEAM", "EVENT_WORK")]
    preds, _ = batch_decode([{"eng": x["cell_value"]} for x in sample])
    out = []
    for x, pr in zip(sample, preds):
        out.append({"id": x["example_id"], "surface": x["cell_value"], "byt5_pred": pr,
                    "category": x["candidate_type"]})
    with (HERE / "results" / "eval_sample_named.jsonl").open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("sample NAMED_ENTITY preds:", len(out))


if __name__ == "__main__":
    main()
