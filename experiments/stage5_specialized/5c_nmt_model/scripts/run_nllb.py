"""Experiment 5C - NLLB-200-distilled-600M (transformers 5.x: manual generate)."""
from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
os.environ.setdefault("HF_HOME", str(HERE.parent / ".cache" / "hf"))
print("HF_HOME:", os.environ["HF_HOME"], flush=True)

import torch  # noqa: E402
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: E402

TARGET_ITEMS = HERE / "results" / "commonword_no_coverage.json"
OUT = HERE / "results" / "nllb_600m_results.jsonl"
STATS = HERE / "results" / "nllb_600m_stats.json"
MODEL_NAME = "facebook/nllb-200-distilled-600M"


def main():
    items = json.loads(TARGET_ITEMS.read_text(encoding="utf-8"))
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, dtype=torch.float16).to("cuda")
    model.eval()
    load_s = round(time.time() - t0, 1)
    bos_rus = tok.convert_tokens_to_ids("rus_Cyrl")
    lat = []
    out = []
    for it in items:
        t0 = time.time()
        try:
            enc = tok(it["surface"], return_tensors="pt").to("cuda")
            gen = model.generate(**enc, forced_bos_token_id=bos_rus, max_length=256, num_beams=4)
            ru = tok.batch_decode(gen, skip_special_tokens=True)[0]
            err = None
        except Exception as e:
            ru, err = None, f"{type(e).__name__}: {e}"
        lat.append(time.time() - t0)
        out.append({"id": it["id"], "source": it["surface"], "nllb_ru": ru,
                    "error": err, "latency_s": round(time.time() - t0, 2)})
        print(it["id"], "|", it["surface"][:44], "->", (ru or err)[:70], flush=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lat.sort()
    stats = {
        "model": MODEL_NAME, "device": "cuda fp16, beams=4", "n": len(out),
        "load_s": load_s,
        "latency_mean_s": round(statistics.mean(lat), 2),
        "latency_median_s": round(statistics.median(lat), 2),
        "latency_p95_s": round(lat[int(0.95 * len(lat))], 2) if len(lat) > 1 else lat[0],
        "total_runtime_s": round(sum(lat), 1),
        "model_revision_note": "revision recorded in DATASET_INFO.md",
    }
    STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
