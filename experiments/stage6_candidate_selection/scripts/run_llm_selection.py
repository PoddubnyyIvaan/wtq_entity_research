"""Stage 6 — LLM candidate selection (NO generation allowed).

One unified prompt; answer must be candidate_id or NO_MATCH, JSON only.
Runs: mode D on all candidates>0 examples for qwen2.5:3b and qwen2.5:7b;
context ablation A-E; oracle set; shuffled-context control.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "02_llm_experiments" / "scripts"))

BASE = "http://localhost:11434/v1"
TEMP = 0.0
MAXTOK = 120
PROMPT_V = "stage6_v2"

TEMPLATE = """Select the candidate that represents the SAME entity as the source value.

SOURCE ENTITY:
{surface}

CONTEXT:
column header = {column}
row = {row}
WTQ question = {question}
table title = {title}

CANDIDATES:
{cands}

TASK:
Select the candidate that best represents the same entity and is appropriate
for this WTQ context. You MUST select one of the provided candidate IDs or
return NO_MATCH. You MUST NOT generate, modify, transliterate, combine,
normalize, reorder, or rewrite any candidate — the final answer will copy
the selected candidate verbatim.

Return JSON only.
If you choose candidate_02, return exactly: {"selection": "candidate_02", "confidence": 0.8}
If no candidate fits, return: {"selection": "NO_MATCH", "confidence": 0.7}
Never write anything inside "selection" except an existing candidate_id
(like candidate_01) or the exact word NO_MATCH.
"""


def chat(user_text, model, retries=2):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": user_text}],
                       "temperature": TEMP, "max_tokens": MAXTOK}).encode()
    err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(BASE + "/chat/completions", body,
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                obj = json.loads(r.read())
            return obj["choices"][0]["message"]["content"], obj.get("usage", {}), None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1))
    return None, {}, err


def parse_sel(text):
    if text is None:
        return None
    t = text.strip().replace("{{", "{").replace("}}", "}")
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        j = json.loads(t)
    except Exception:
        i, k = t.find("{"), t.rfind("}")
        if 0 <= i < k:
            try:
                j = json.loads(t[i:k + 1])
            except Exception:
                return None
        else:
            return None
    sel = str(j.get("selection", "")).strip()
    conf = j.get("confidence")
    return {"selection": sel, "confidence": conf}


def fmt_cands(cands):
    out = []
    for c in cands:
        out.append(f"[{c['candidate_id']}]\nRussian form: {c['ru_form']}\n"
                   f"source: {c['source'].upper()}" + (f"\nQID: {c['qid']}" if c.get("qid") else ""))
    return "\n\n".join(out)


def context_of(it_sample, mode, shuffle_ctx=None):
    ctx = it_sample["context"] if "context" in it_sample else None
    column = ctx.get("column") or "not available"
    row = (ctx.get("row") or "")[:160] or "not available"
    question = ctx.get("question") or "not available"
    title = ctx.get("page_title") or "not available"
    if shuffle_ctx:
        column, row, question, title = shuffle_ctx
    if mode == "A":
        return "not available", "not available", "not available", "not available"
    if mode == "B":
        return column, "not available", "not available", "not available"
    if mode == "C":
        return column, row, "not available", "not available"
    if mode == "D":
        return column, row, question, "not available"
    if mode == "E":
        return column, row, question, title
    return column, row, question, title


def run_tag(model, mode, tag, oracle=False, shuffle_map=None, limit=None, run_ids=None):
    sets = [json.loads(l) for l in (HERE / "candidate_sets.jsonl").open()]
    sample = {x["example_id"]: x for x in map(json.loads, (ROOT / "samples" / "sample200.jsonl").open())}
    oracle_file = HERE / "oracle_sets.jsonl"
    oracle = {r["id"]: r for r in map(json.loads, oracle_file.open())} if oracle_file.exists() else {}
    rows = []
    lat = []
    n = 0
    for s in sets:
        if run_ids is not None and s["id"] not in run_ids:
            continue
        if not s["candidates"]:
            continue
        sid = s["id"]
        cands = s["candidates"]
        if oracle and sid in oracle:
            cands = oracle[sid]["candidates"]
        shuf = shuffle_map.get(sid) if shuffle_map else None
        col, row, q, ti = context_of(s, mode, shuf)
        prompt = (TEMPLATE.replace("{cands}", fmt_cands(cands))
                  .replace("{surface}", s["surface"])
                  .replace("{column}", col).replace("{row}", row)
                  .replace("{question}", q).replace("{title}", ti))
        t0 = time.time()
        resp, usage, err = chat(prompt, model)
        lat.append(time.time() - t0)
        j = None
        sel = None
        if resp:
            i, k = resp.find("{"), resp.rfind("}")
            if 0 <= i < k:
                try:
                    j = json.loads(resp[i:k + 1])
                    sel = str(j.get("selection", ""))
                except Exception:
                    j = None
        valid = {c["candidate_id"] for c in cands}
        if sel == "NO_MATCH":
            status = "NO_MATCH"
        elif sel in valid:
            status = "SELECTED"
        elif sel is None:
            status = "PARSE_FAIL"
        else:
            status = "INVALID_SELECTION"
        rows.append({"id": sid, "mode": mode, "tag": tag, "model": model,
                     "n_candidates": len(cands),
                     "selection": sel, "status": status,
                     "confidence": (j or {}).get("confidence") if j else None,
                     "selected_ru": next((c["ru_form"] for c in cands if c["candidate_id"] == sel), None),
                     "raw": (resp or "")[:400], "error": err,
                     "latency_s": round(time.time() - t0, 2)})
        n += 1
        if n % 50 == 0:
            print(f"{tag} {model} {mode}: {n} done", flush=True)
    out = HERE / "raw" / {"qwen2.5:3b": "qwen3b", "qwen2.5:7b": "qwen7b"}[model]
    out.mkdir(exist_ok=True)
    fn = out / f"sel_{tag}_{mode}.jsonl"
    with fn.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"saved {len(rows)} -> {fn.name}; mean lat {statistics.mean(lat):.2f}s", flush=True)
    return rows


def main():
    model = sys.argv[1]
    mode = sys.argv[2]
    tag = sys.argv[3]
    ids_arg = sys.argv[4] if len(sys.argv) > 4 else None
    run_ids = set(json.loads(Path(ids_arg).read_text())) if ids_arg else None
    smap = None
    if tag == "shuffled":
        mp = Path(__file__).resolve().parents[1] / "shuffled_map.json"
        smap = {k: v for k, v in json.loads(mp.read_text(encoding="utf-8")).items()}
    run_tag(model, mode, tag, run_ids=run_ids, shuffle_map=smap)


if __name__ == "__main__":
    main()
