"""Experiment 6E - LLM judge (qwen2.5:3b) on Experiment 1 Mode-D translations.

Judge is NOT a resolver: it only assesses an existing translation.
Runs on all 200 (mode D) + archive latencies, and the 40-example manual
subset is extracted for comparison with rule-based QC and manual verdicts.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from exp1_context import chat, parse_json_loose, MODEL  # noqa

TEMPLATE = (ROOT / "prompts" / "judge_v1.txt").read_text(encoding="utf-8")


def main():
    rows = [json.loads(l) for l in (ROOT / "results" / "exp1_llm_context.jsonl").open()]
    drows = {r["example_id"]: r for r in rows if r["mode"] == "D"}
    sample = {x["example_id"]: x for x in
              (json.loads(l) for l in (ROOT / "samples" / "sample200.jsonl").open())}
    lat = []
    out = []
    for i, (eid, r) in enumerate(drows.items()):
        it = sample[eid]
        row = " | ".join(v for v in it["row_context"].values() if v)[:200]
        user = TEMPLATE.replace("{source}", r["source"]) \
            .replace("{translation}", r["translation"] or "(empty)") \
            .replace("{column}", it["column_header"] or "not available") \
            .replace("{row}", row or "not available") \
            .replace("{title}", it["table_caption_or_title"] or it["page_title"] or "not available") \
            .replace("{question}", it["question_context"] or "not available")
        t0 = time.time()
        resp, usage, err = chat(user)
        lat.append(time.time() - t0)
        parsed = parse_json_loose(resp)
        out.append({
            "example_id": eid, "source": r["source"], "llm_translation": r["translation"],
            "model": MODEL, "prompt_version": "judge_v1",
            "judge": parsed, "parse_ok": parsed is not None,
            "error": err, "latency_s": round(time.time() - t0, 2),
            "raw_response": (resp or "")[:1000],
        })
        if (i + 1) % 20 == 0:
            print(f"judge {i+1}/200", flush=True)
            save(out)
    save(out)
    lat.sort()
    parse_ok = sum(1 for r in out if r["parse_ok"])
    flagged = sum(1 for r in out if r["judge"] and r["judge"].get("needs_review"))
    harmful = sum(1 for r in out if r["judge"] and r["judge"].get("harmful_substitution"))
    stats = {
        "n": len(out), "parse_success": parse_ok / len(out),
        "harmful_substitution_rate": harmful / len(out),
        "needs_review_rate": flagged / len(out),
        "latency_mean_s": round(statistics.mean(lat), 2),
        "latency_median_s": round(statistics.median(lat), 2),
        "latency_p95_s": round(lat[int(0.95 * len(lat))], 2),
        "total_runtime_s": round(sum(lat), 1),
        "model": MODEL, "prompt": "judge_v1",
    }
    (ROOT / "results" / "exp6e_llm_judge_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))


def save(out):
    with (ROOT / "results" / "exp6e_llm_judge.jsonl").open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
