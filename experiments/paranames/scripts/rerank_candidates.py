"""Variant B - Qwen reranks existing ParaNames candidates (no generation).

Prompt asks ONLY to pick candidate_id or NO_MATCH. Applied to the
multiple-candidates cases of the sample.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from exp1_context import chat, parse_json_loose, MODEL  # noqa

TEMPLATE = """You are helping select, NOT translate, a Russian name for an entity from a table.

English name: {eng}
Candidates (bai id: Russian form):
{list}

Context:
column header = {column}
row = {row}
WTQ question = {question}

Task: pick the candidate that best fits this table context. If unsure, answer NO_MATCH.

Rules:
- Do NOT generate a new translation.
- Do NOT modify candidates.
- Return JSON only: {{"candidate_id": <number>|null, "answer": "<candidate number>|NO_MATCH"}}
"""


def main():
    rows = [json.loads(l) for l in (HERE / "paranames_results.jsonl").open()]
    out = []
    for r in rows:
        if r["paranames_match_type"] != "multiple":
            continue
        c_list = r["paranames_candidates"][:6]
        listing = "\n".join(f"{i + 1}. {c['ru']} ({c['type']})"
                            for i, c in enumerate(c_list))
        ctx = r["context"]
        prompt = TEMPLATE.replace("{eng}", r["source_surface"]) \
            .replace("{list}", listing) \
            .replace("{column}", ctx.get("column") or "not available") \
            .replace("{row}", (ctx.get("row") or "")[:200] or "not available") \
            .replace("{question}", ctx.get("question") or "not available")
        resp, usage, err = chat(prompt)
        j = parse_json_loose(resp)
        pick = None
        if j:
            try:
                n = int(str(j.get("answer", "")).strip())
                if 1 <= n <= len(c_list):
                    pick = c_list[n - 1]["ru"]
            except Exception:
                pick = None
        out.append({
            "id": r["id"], "source": r["source_surface"],
            "cands": [c["ru"] for c in c_list],
            "qwen_pick": j.get("answer") if j else None,
            "qwen_pick_ru": pick,
            "selected": pick or r["paranames_selected"],
            "raw": (resp or "")[:400], "error": err,
        })
    with (HERE / "results_rerank.json").open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("reranked:", len(out))
    for o in out:
        print(o["id"], o["source"][:24], "| cands:", o["cands"][:4], "| pick:", o["qwen_pick"], o["selected"])


if __name__ == "__main__":
    main()
