"""Re-run Experiment 6E judge (same prompt judge_v1) with qwen2.5:7b on the
5B localizer outputs — direct comparison with the qwen2.5:3b judge numbers.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "02_llm_experiments" / "scripts"))
from exp1_context import chat, parse_json_loose  # noqa

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b"
OUT = HERE / "results" / f"judge_{MODEL.replace(':', '_')}.jsonl"
STATS = HERE / "results" / f"judge_{MODEL.replace(':', '_')}_stats.json"
TEMPLATE = (ROOT / "experiments" / "02_llm_experiments" / "prompts" / "judge_v1.txt").read_text(encoding="utf-8")


def save(out):
    with OUT.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    sample = {x["example_id"]: x for x in map(json.loads, (ROOT / "samples" / "sample200.jsonl").open())}
    rows = [json.loads(l) for l in (HERE / "results" / f"localizer_{MODEL.replace(':', '_')}.jsonl").open()]
    lat = []
    out = []
    for i, r in enumerate(rows):
        it = sample[r["id"]]
        row = " | ".join(v for v in it["row_context"].values() if v)[:200]
        u = TEMPLATE.replace("{source}", r["source"]) \
            .replace("{translation}", r["llm_translation"] or "(empty)") \
            .replace("{column}", it["column_header"] or "not available") \
            .replace("{row}", row or "not available") \
            .replace("{title}", it["table_caption_or_title"] or it["page_title"] or "not available") \
            .replace("{question}", it["question_context"] or "not available")
        t0 = time.time()
        resp, usage, err = chat(u)
        lat.append(time.time() - t0)
        j = parse_json_loose(resp)
        out.append({"id": r["id"], "source": r["source"], "llm_translation": r["llm_translation"],
                    "model": MODEL, "prompt_version": "judge_v1",
                    "judge": j, "parse_ok": j is not None, "error": err,
                    "latency_s": round(time.time() - t0, 2),
                    "raw_response": (resp or "")[:800]})
        if (i + 1) % 50 == 0:
            print(f"judge {i + 1}/200", flush=True)
            save(out)
    save(out)
    lat.sort()
    parse_ok = sum(1 for r in out if r["parse_ok"])
    stats = {"model": MODEL, "n": len(out), "parse_success": parse_ok / len(out),
             "needs_review_rate": sum(1 for r in out if r["judge"] and r["judge"].get("needs_review")) / len(out),
             "harmful_substitution_rate": sum(1 for r in out if r["judge"] and r["judge"].get("harmful_substitution")) / len(out),
             "latency_mean_s": round(statistics.mean(lat), 2),
             "latency_median_s": round(statistics.median(lat), 2),
             "latency_p95_s": round(lat[int(0.95 * len(lat))], 2),
             "total_runtime_s": round(sum(lat), 1), "prompt": "judge_v1"}
    STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
