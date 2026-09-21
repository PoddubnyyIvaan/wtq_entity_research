"""Experiment 5B - larger local LLM as localizer (RAG-grounded).

Given resolver candidates (Wikidata ru_form / ParaNames candidates), the model
must CONFIRM / adjust formatting / return NO_CANDIDATE. Free generation is
forbidden by the schema (answer must be one of the candidates or NO_CANDIDATE).
Run with qwen2.5:7b (optional: 14b) and compared to qwen2.5:3b stage-2 results.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "02_llm_experiments" / "scripts"))

BASE = "http://localhost:11434/v1"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b"
OUT = HERE / "results" / f"localizer_{MODEL.replace(':', '_')}.jsonl"
STATS = HERE / "results" / f"localizer_{MODEL.replace(':', '_')}_stats.json"

TEMPLATE = """You are checking a Russian translation candidate for one cell of an English table.

Cell (English): {cell}
Column header: {column}
Row: {row}
WTQ question: {question}

Candidate Russian form(s) from our resolver (top {ncand}):
{cands}

Your task:
- If the candidate(s) correctly translate/transliterate the cell value in this
  context, copy the best one EXACTLY into "translation" (you may only fix
  capitalization, spaces or redundant parentheses like "(значения)").
- Do NOT invent a new translation. Do NOT modify the wording of a candidate.
- If NO candidate fits, set "translation" to "NO_CANDIDATE".

Return JSON only, with SINGLE braces, for example:
{"source": "Parent", "translation": "Родитель", "confidence": 0.9, "reason": "..."}
"""


def chat(user_text, retries=2):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": user_text}],
                       "temperature": 0.0, "max_tokens": 200}).encode()
    err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(BASE + "/chat/completions", body,
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                obj = json.loads(r.read())
            return obj["choices"][0]["message"]["content"], obj.get("usage", {}), None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1))
    return None, {}, err


def parse_json_loose(text):
    if text is None:
        return None
    t = text.strip().replace("{{", "{").replace("}}", "}")
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        return json.loads(t)
    except Exception:
        i, j = t.find("{"), t.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                return None
    return None


def resolver_candidates(it, e2, e3, pn):
    cands = []
    if e2.get("ru_form"):
        cands.append({"ru": e2["ru_form"], "source": "wikidata"})
    pn_ru = None
    for r in pn:
        if r["id"] == it["example_id"] and r["paranames_candidates"]:
            pn_ru = r["paranames_candidates"][0]["ru"]
    if pn_ru and (not cands or " ".join(pn_ru.split()).casefold() != " ".join(cands[0]["ru"].split()).casefold()):
        cands.append({"ru": pn_ru, "source": "paranames"})
    return cands[:3]


def main():
    sample = [json.loads(l) for l in (ROOT / "samples" / "sample200.jsonl").open()]
    exp2 = {r["example_id"]: r for r in map(json.loads, (ROOT / "results" / "exp2_wikidata.jsonl").open())}
    pn = [json.loads(l) for l in (ROOT / "experiments" / "paranames" / "paranames_results.jsonl").open()]
    lat = []
    rows = []
    t_start = time.time()
    for i, it in enumerate(sample):
        e2 = exp2.get(it["example_id"], {})
        cands = resolver_candidates(it, e2, None, pn)
        cand_txt = "\n".join(f"{j + 1}. {c['ru']} [{c['source']}]" for j, c in enumerate(cands)) \
            if cands else "NO_CANDIDATE_AVAILABLE"
        prompt = (TEMPLATE.replace("{cell}", it["cell_value"])
                  .replace("{column}", it["column_header"] or "not available")
                  .replace("{row}", " | ".join(v for v in it["row_context"].values() if v)[:160] or "not available")
                  .replace("{question}", it["question_context"] or "not available")
                  .replace("{ncand}", str(len(cands)) if cands else "0")
                  .replace("{cand_list}", cand_list := cand_txt))
        t0 = time.time()
        resp, usage, err = chat(prompt)
        lat.append(time.time() - t0)
        j = parse_json_loose(resp)
        rows.append({
            "id": it["example_id"], "source": it["cell_value"],
            "candidates": cands, "model": MODEL,
            "llm_translation": (j or {}).get("translation"),
            "confidence": (j or {}).get("confidence"),
            "is_no_candidate": ((j or {}).get("translation") == "NO_CANDIDATE"),
            "parse_ok": j is not None, "error": err,
            "latency_s": round(time.time() - t0, 2),
            "raw_response": (resp or "")[:500],
        })
        if (i + 1) % 25 == 0:
            print(f"{MODEL} localizer {i+1}/200 elapsed={int(time.time()-t_start)}s", flush=True)
            save(rows, OUT)
    save(rows, OUT)
    parse_ok = sum(1 for r in rows if r["parse_ok"])
    nocand = sum(1 for r in rows if r["is_no_candidate"])
    lat.sort()
    stats = {
        "model": MODEL, "n": len(rows), "parse_success": parse_ok / len(rows),
        "no_candidate_rate": nocand / len(rows),
        "latency_mean_s": round(statistics.mean(lat), 2),
        "latency_median_s": round(statistics.median(lat), 2),
        "latency_p95_s": round(lat[int(0.95 * len(lat))], 2),
        "total_runtime_s": round(sum(lat), 1),
        "temperature": 0.0, "max_tokens": 200,
        "gpu_check": "ollama ps: size_vram == model size (full GPU offload), see stage5 report",
    }
    STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))


def save(rows, path):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
