"""Shared utilities for the four EN->RU dictionary experiments."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parents[0]          # experiments/dictionaries
ROOT = HERE.parents[1]                              # wtq_entity_research
sys.path.insert(0, str(ROOT / "scripts"))

SAMPLE = (ROOT / "samples" / "sample200.jsonl")

CATEGORY_MAP = {
    "PERSON": "NAMED_ENTITY", "SURNAME": "NAMED_ENTITY", "LOCATION": "NAMED_ENTITY",
    "ORGANIZATION": "NAMED_ENTITY", "SPORTS_TEAM": "NAMED_ENTITY",
    "EVENT_WORK": "NAMED_ENTITY", "MULTI_WORD": "COMMON_WORD",
    "SHORT_AMBIGUOUS": "COMMON_WORD", "FALSE_POSITIVE": "COMMON_WORD",
    "UNKNOWN": "UNKNOWN",
}


def norm(s: str) -> str:
    """Case/punct/whitespace/unicode normalize, diacritics kept differences."""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("´", "'")
    s = s.strip().strip(" @").strip()
    return " ".join(s.split()).casefold()


def classify(cat_type: str, value: str) -> str:
    if re.search(r"\d", value) and len(value) <= 6:
        return "NUMBER"
    if any(ch.isdigit() for ch in value) and not re.search(r"[A-Za-z]{3}", value):
        return "JUNK"
    t = CATEGORY_MAP.get(cat_type, "UNKNOWN")
    if value.strip().casefold() in {"n/a", "na", "tbd", "tba", "none", "unknown", "—", "-", "–"}:
        return "JUNK"
    return t


def strip_dsl_tags(s: str) -> str:
    s = re.sub(r"\[c[^\]]*\][^\[]*\[/c\]", "", s)      # pronunciation/gray
    s = re.sub(r"\[p\][^[]*\[/p\]", "", s)             # POS tags
    s = re.sub(r"\[[^\]]+\]", "", s)                   # other DSL tags
    s = s.replace("\\[", "[").replace("\\]", "]")
    return s


def parse_dsl_cards(lines):
    """Yield (headword, [card_text, ...]) pairs from DSL line list."""
    entries = []
    cur_head = None
    cur_cards = []
    for ln in lines:
        if not ln.strip():
            continue
        if ln.startswith("#") and not ln.startswith("#!"):
            continue
        if not ln.startswith("\t") and not ln.startswith(" "):
            # new entry headword
            if cur_head is not None:
                entries.append((cur_head, cur_cards))
            cur_head = ln.strip()
            cur_cards = []
        else:
            if cur_head is not None:
                cur_cards.append(ln.strip())
    if cur_head is not None:
        entries.append((cur_head, cur_cards))
    return entries


def cyrillic_runs(s: str):
    return re.findall(r"[А-Яа-яЁё][А-Яа-яЁё \-']*", s)


def context_of(it):
    return {
        "column": it["column_header"],
        "row": " | ".join(v for v in it["row_context"].values() if v)[:200],
        "question": it["question_context"] or None,
    }


def load_sample():
    return [json.loads(l) for l in (ROOT / "samples" / "sample200.jsonl").open()]


def category_of(it):
    v = it["cell_value"]
    t = it["candidate_type"]
    if re.fullmatch(r"\d[\d.,%\- ]*", v):
        return "NUMBER"
    if any(ch.isdigit() for ch in v):
        return "JUNK"
    if t == "FALSE_POSITIVE":
        return "COMMON_WORD"
    if t in ("PERSON", "SURNAME", "LOCATION", "ORGANIZATION", "SPORTS_TEAM", "EVENT_WORK"):
        return "NAMED_ENTITY"
    if t == "MULTI_WORD":
        return "COMMON_WORD"
    if t == "SHORT_AMBIGUOUS":
        return "COMMON_WORD"
    return "UNKNOWN"


def write_results(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def stats_of(rows, extra=None):
    from collections import Counter
    st = {
        "total": len(rows),
        "unique_forms": len({r["normalized_surface"] for r in rows}),
        "match_type": dict(Counter(r["match_type"] for r in rows)),
        "decision": dict(Counter(r["decision"] for r in rows)),
        "category": dict(Counter(r["category"] for r in rows)),
        "category_match": {
            c: {
                "matched": sum(1 for r in rows if r["category"] == c and r["match_type"] != "none"),
                "n": sum(1 for r in rows if r["category"] == c),
            } for c in ("COMMON_WORD", "NAMED_ENTITY", "NUMBER", "JUNK", "UNKNOWN")
        },
    }
    if extra:
        st.update(extra)
    return st
