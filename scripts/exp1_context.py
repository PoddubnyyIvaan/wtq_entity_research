"""Experiment 1 - context ablation (modes A-D) with local Ollama qwen2.5:3b.

prompt_v2 (prompts/exp1_v2.txt). LLM states interpretation/is_entity/confidence;
Wikidata evidence (exp2) is merged EXTERNALLY afterwards, never trusted from LLM.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost:11434/v1"
MODEL = "qwen2.5:3b"
TEMPERATURE = 0.0
MAX_TOKENS = 350
PROMPT_V = "prompt_v2"
ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))

TEMPLATE = (ROOT / "prompts" / "exp1_v2.txt").read_text(encoding="utf-8")


def chat(user_text, retries=2):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": user_text}],
                       "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS}).encode()
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(BASE + "/chat/completions", body,
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                obj = json.loads(r.read())
            content = obj["choices"][0]["message"]["content"]
            usage = obj.get("usage", {})
            return content, usage, None
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(3 * (attempt + 1))
    return None, {"usage": {}}, last_err


def parse_json_loose(text):
    if text is None:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:]
    t = t.strip()
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


def build_prompt(mode, cell, column, row_ctx, question, title):
    row = row_ctx if isinstance(row_ctx, str) else \
        (" | ".join(v for v in (row_ctx or {}).values() if v) if row_ctx else "not available")
    return TEMPLATE.replace("{cell}", cell or "not available") \
        .replace("{column}", column or "not available") \
        .replace("{row}", row or "not available") \
        .replace("{question}", question or "not available") \
        .replace("{title}", title or "not available")


def make_context(mode, sample_item):
    cell = sample_item["cell_value"]
    column = sample_item["column_header"]
    row_ctx = sample_item["row_context"]
    question = sample_item["question_context"]
    title = sample_item["table_caption_or_title"] or sample_item["page_title"]
    if mode == "A":
        return cell, "not available", "not available", "not available", "not available"
    if mode == "B":
        return cell, column, "not available", "not available", "not available"
    if mode == "C":
        return cell, "not available", row_ctx, "not available", "not available"
    return cell, column, row_ctx, question, title  # D


def run(items, tag):
    rows = []
    t_start = time.time()
    lat = []
    for i, it in enumerate(items):
        for mode in "ABCD":
            cell, column, row_ctx, question, title = make_context(mode, it)
            user = build_prompt(mode, cell, column, row_ctx, question, title)
            t0 = time.time()
            resp, usage, err = chat(user_text=user_text(user_text_slot := user))
            lat.append(time.time() - t0)
            parsed = parse_json_loose(resp)
            rows.append({
                "example_id": it["example_id"], "mode": mode, "source": it["cell_value"],
                "header": column if column != "not available" else "",
                "prompt_version": PROMPT_V,
                "model": MODEL, "temperature": TEMPERATURE,
                "translation": (parsed or {}).get("translation", ""),
                "is_entity": (parsed or {}).get("is_entity"),
                "entity_type": (parsed or {}).get("entity_type", ""),
                "interpretation": (parsed or {}).get("interpretation", ""),
                "confidence": (parsed or {}).get("confidence"),
                "needs_review": (parsed or {}).get("needs_review"),
                "parse_ok": parsed is not None,
                "error": err, "latency_s": round(time.time() - t0, 2),
                "tokens": usage.get("total_tokens") if usage else None,
                "raw_response": (resp or "")[:1200],
            })
        if (i + 1) % 10 == 0:
            print(f"exp1: {i+1}/{len(items)} elapsed={int(time.time()-t_start)}s", flush=True)
            save(rows, ROOT / "results" / f"exp1_llm_context{TAG}.jsonl")
    save(rows, ROOT / "results" / f"exp1_llm_context{TAG}.jsonl")
    return rows


def save(rows, path):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def user_text(user_text_slot):
    return user_text_slot


def main():
    global PROMPT_V, TAG
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    tag = sys.argv[2] if len(sys.argv) > 2 else ""
    TAG = tag
    items = [json.loads(l) for l in (ROOT / "samples" / "sample200.jsonl").open()]
    items = items[:limit]
    rows = run(items, tag)
    parse_ok = sum(1 for r in rows if r["parse_ok"])
    errs = sum(1 for r in rows if r["error"])
    lat = [r["latency_s"] for r in rows if r["latency_s"]]
    lat.sort()
    p95 = lat[int(0.95 * len(lat))] if lat else 0
    stats = {
        "n": len(rows), "model": MODEL, "prompt": PROMPT_V, "temperature": TEMPERATURE,
        "parse_success": parse_ok / len(rows), "http_errors": errs,
        "latency_mean_s": round(statistics.mean(lat) if lat else 0, 2),
        "latency_median_s": round(statistics.median(lat) if lat else 0, 2),
        "latency_p95_s": round(p95, 2),
        "total_runtime_s": round(sum(lat), 1),
    }
    (ROOT / "results" / f"exp1_llm_context{tag or ''}_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
