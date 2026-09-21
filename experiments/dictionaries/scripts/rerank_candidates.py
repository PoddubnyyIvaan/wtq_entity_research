"""Optional contextual reranking: Qwen2.5:3b selects among dictionary candidates.

Only cases with >=2 candidates. LLM may only answer candidate number or
NO_MATCH; no generation. Results saved separately per dictionary.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from exp1_context import chat, parse_json_loose  # noqa

TEMPLATE = """Select the Russian candidate that fits the table context best.

English value: {surface}
Candidates:
{list}

Context:
column header = {column}
row = {row}
question = {question}

Rules:
- Only choose among the candidates above. Do NOT generate a new translation.
- If unsure, answer NO_MATCH.
- If you choose candidate 2, return JSON {{"answer": "2"}}. If unsure, return {{"answer": "NO_MATCH"}}.
"""


def main():
    tasks = []
    for d, res in [("wikidict", HERE / "wikidict" / "results.jsonl"),
                   ("wiktionary", HERE / "wiktionary" / "results.jsonl"),
                   ("openrussian", HERE / "openrussian" / "results.jsonl"),
                   ("statistical_full", HERE / "statistical" / "results_full.jsonl"),
                   ("statistical_filtered", HERE / "statistical" / "results_filtered.jsonl")]:
        for r in map(json.loads, res.open()):
            if r["match_type"] == "multiple" and len(r["candidates"]) >= 2:
                tasks.append((d, r))
    tasks = tasks[:80]
    print("rerank tasks:", len(tasks), flush=True)
    lat = []
    out = []
    for i, (d, r) in enumerate(tasks):
        listing = "\n".join(f"{j + 1}. {c['ru']}" for j, c in enumerate(r["candidates"][:6]))
        ctx = r["context"]
        prompt = TEMPLATE.replace("{surface}", r["source_surface"]) \
            .replace("{list}", listing) \
            .replace("{column}", ctx.get("column") or "not available") \
            .replace("{row}", (ctx.get("row") or "")[:160] or "not available") \
            .replace("{question}", ctx.get("question") or "not available")
        resp, usage, err = chat(prompt)
        lat.append(time.time() if False else 0)
        j = parse_json_loose(resp)
        pick = None
        if j:
            ans = str(j.get("answer", ""))
            m = re.search(r"\d+", ans)
            if m and "NO_MATCH" not in ans.upper():
                n = int(m.group(0))
                if 1 <= n <= len(r["candidates"]):
                    pick = r["candidates"][n - 1]["ru"]
            elif "NO_MATCH" in ans.upper():
                pick = None
                j["answer"] = "NO_MATCH"
        out.append({"id": r["id"], "dictionary": d, "surface": r["source_surface"],
                    "candidates": [c["ru"] for c in r["candidates"]],
                    "qwen_answer": (j or {}).get("answer"), "qwen_pick_ru": pick,
                    "error": err})
        if (i + 1) % 20 == 0:
            print(f"rerank {i+1}/{len(tasks)}", flush=True)
    (HERE / "rerank_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    numeric = sum(1 for o in out if isinstance(o["qwen_pick_ru"], str))
    no_match = sum(1 for o in out if (o["qwen_answer"] or "").strip().upper() == "NO_MATCH")
    bad_format = len(out) - numeric - no_match
    print(json.dumps({"tasks": len(out), "numeric_pick": numeric, "no_match": no_match,
                      "format_break": bad_format}, ensure_ascii=False))


import time  # noqa: E402

if __name__ == "__main__":
    main()
