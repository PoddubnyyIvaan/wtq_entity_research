"""LLM smoke tests (Ollama qwen2.5:3b): translation, JSON stability, context sensitivity."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost:11434/v1"
MODEL = "qwen2.5:3b"
RESEARCH = Path(__file__).resolve().parents[1]


def chat(messages, temperature=0.0, max_tokens=300):
    body = json.dumps({"model": MODEL, "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(BASE + "/chat/completions", body,
                                 {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=240) as r:
        obj = json.loads(r.read())
    dt = time.time() - t0
    return obj["choices"][0]["message"]["content"], dt, obj.get("usage", {})


def parse_json_loose(text: str):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        # first {...} block
        i, j = t.find("{"), t.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                return None
    return None


def main():
    out = {"results": []}

    # Test 1: simple translation
    r = chat([{"role": "user", "content": "Translate:\nNew York\n\nReturn only the Russian translation."}])
    t1 = {"test": "simple_translation", "latency_s": round(dt_ok(r), 2),
          "raw": r[0] if isinstance(r, tuple) else r}
    resp = r[0] if isinstance(r, tuple) else r
    t1["contains_nyork"] = "Нью-Йорк" in resp
    out["results"].append(t1)
    print("Test1 raw:", resp[:120], "| NY ok:", t1["contains_nyork"], flush=True)

    # Test 2: structured JSON
    prompt = ("Translate a cell from an English table into Russian.\n\n"
              "Cell:\nBuffalo Bills\n\nColumn:\nLosing Team\n\n"
              "Return JSON only with keys: translation, entity_type, interpretation.")
    r2 = chat([{"role": "user", "content": prompt}])
    resp2 = r2[0]
    j = parse_json_loose(resp2)
    t2 = {"test": "structured_json", "parsed": j is not None, "raw": resp2}
    out["results"].append(t2)
    print("Test2 parsed:", j, flush=True)

    # Test 3: context sensitivity (with/without context)
    cases = [
        ("Smith", {}, "cell only"),
        ("Smyth", {}, "cell only"),
        ("Smith", {"column": "Player", "row": "Smith | New York | 1998", "question": "who scored the first goal?"}, "with context"),
        ("Smyth", {"column": "Player", "row": "Smyth | New York | 1998", "question": "who scored the first goal?"}, "with context"),
        ("Arsenal", {}, "cell only"),
        ("Arsenal", {"column": "Club", "row": "Arsenal | London | 1998", "question": "which club won?"}, "with context"),
        ("Washington", {}, "cell only"),
        ("Washington", {"column": "Birthplace", "row": "Denzel | Washington | 1954", "question": "where was the actor born?"}, "with context"),
        ("Giants", {}, "cell only"),
        ("Red Box", {}, "cell only"),
        ("Red Box", {"column": "Band", "row": "Red Box | Lean On Me | 1985", "question": "which band released this song?"}, "with context"),
    ]
    for val, ctx, note in cases:
        parts = [f"Cell:\n{val}"]
        if ctx.get("column"):
            parts.append(f"\nColumn:\n{ctx['column']}")
        if ctx.get("row"):
            parts.append(f"\nRow:\n{ctx['row']}")
        if ctx.get("question"):
            parts.append(f"\nWTQ question:\n{ctx['question']}")
        p = (parts[0] + "".join(parts[1:]) + "\n\nReturn JSON only with keys: translation, entity_type, interpretation, needs_review.")
        r3 = chat([{"role": "user", "content": p}])
        j3 = parse_json_loose(r3[0])
        out["results"].append({"test": "context_sensitivity", "cell": val, "ctx": note,
                               "parsed": j3, "raw": r3[0][:400]})
        print(f"Test3 {val!r:24s} [{note:12s}] -> {json.dumps(j3, ensure_ascii=False)[:160]}", flush=True)

    RESEARCH = Path(__file__).resolve().parents[1]
    (RESEARCH / "results" / "llm_smoke_test.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("saved results/llm_smoke_test.json", flush=True)


def dt_ok(x):
    return 0


if __name__ == "__main__":
    main()
