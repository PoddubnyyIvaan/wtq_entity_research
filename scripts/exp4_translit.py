"""Experiment 4 - Rule-based EN->RU transliteration baseline.

Compact rule set (BGN/PCGN-like) for personal names and geographic names,
plus a small traditional-forms dictionary for known conventional renderings.
Evaluated only against the subsets where Wikidata gave a high-confidence
identity match (score>=0.9, cyrillic RU form, no ambiguity flags) — agreement
with Wikidata's conventional form, NOT ground-truth accuracy.

Also checks the Smith/Smyth->Смит collision behavior.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import jdumpl, jdump, norm_key

TRADITIONAL = {
    "london": "Лондон", "new york": "Нью-Йорк", "george": "Джордж", "washington": "Вашингтон",
    "smith": "Смит", "smyth": "Смит", "john": "Джон", "james": "Джеймс", "thomas": "Томас",
    "henry": "Генри", "charles": "Чарльз", "william": "Уильям", "mary": "Мэри", "anna": "Анна",
    "moscow": "Москва", "paris": "Париж", "berlin": "Берлин", "rome": "Рим", "arsenal": "Арсенал",
    "chelsea": "Челси", "toronto": "Торонто", "boston": "Бостон", "chicago": "Чикаго",
    "texas": "Техас", "florida": "Флорида", "california": "Калифорния", "egypt": "Египет",
    "greece": "Греция", "england": "Англия", "scotland": "Шотландия", "wales": "Уэльс",
    "ireland": "Ирландия", "germany": "Германия", "france": "Франция", "spain": "Испания",
    "italy": "Италия", "poland": "Польша", "sweden": "Швеция", "norway": "Норвегия",
    "finland": "Финляндия", "denmark": "Дания", "netherlands": "Нидерланды",
    "switzerland": "Швейцария", "austria": "Австрия", "belgium": "Бельгия",
    "portugal": "Португалия", "japan": "Япония", "china": "Китай", "india": "Индия",
    "brazil": "Бразилия", "australia": "Австралия", "canada": "Канада", "america": "Америка",
}

SKIP_WORDS = {"the", "of", "and", "de", "van", "von", "der", "la", "le", "at", "in"}


def translit_word(w: str) -> str:
    """Simple EN->RU transliteration for one Latin word."""
    s = w.lower()
    out = []
    i = 0
    pairs_single = {
        "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х",
        "i": "и", "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
        "q": "к", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "кс",
        "y": "и", "z": "з", "'": "", "-": "-",
    }
    while i < len(s):
        three = s[i:i + 3]
        two = s[i:i + 2]
        if three == "sch":
            out.append("ш"); i += 3; continue
        if three == "igh":
            out.append("ай"); i += 3; continue
        if s[i:i + 4] == "ough":
            out.append("о"); i += 4; continue
        if two == "th":
            out.append("т"); i += 2; continue
        if two == "ph":
            out.append("ф"); i += 2; continue
        if two == "sh":
            out.append("ш"); i += 2; continue
        if two == "ch":
            out.append("ч"); i += 2; continue
        if two == "ck":
            out.append("к"); i += 2; continue
        if two == "kh":
            out.append("х"); i += 2; continue
        if two == "gh":
            out.append("г"); i += 2; continue
        if two == "oo":
            out.append("у"); i += 2; continue
        if two == "ee":
            out.append("и"); i += 2; continue
        if two == "ea":
            out.append("и"); i += 2; continue
        if two == "ie":
            out.append("и"); i += 2; continue
        if two == "ai":
            out.append("эй"); i += 2; continue
        if two == "ay":
            out.append("эй"); i += 2; continue
        if two == "ou":
            out.append("ау"); i += 2; continue
        if two == "oy" or two == "oi":
            out.append("ой"); i += 2; continue
        if two == "au":
            out.append("о"); i += 2; continue
        if two == "aw":
            out.append("о"); i += 2; continue
        if two == "ow":
            out.append("о"); i += 2; continue
        if two == "qu":
            out.append("кв"); i += 2; continue
        if two == "ew":
            out.append("ью"); i += 2; continue
        if two == "eo":
            out.append("ео"); i += 2; continue
        if two == "ge" and i == len(s) - 2:
            out.append("дж"); i += 2; continue
        if two == "ce" and i == len(s) - 2:
            out.append("с"); i += 2; continue
        if two == "kn" and i == 0:
            out.append("н"); i += 2; continue
        if two == "wr" and i == 0:
            out.append("р"); i += 2; continue
        if s[i] == "y" and i == 0:
            out.append("й"); i += 1; continue
        if s[i] == "y" and i == len(s) - 1:
            out.append("и"); i += 1; continue
        if s[i] == "e" and i == len(s) - 1 and len(s) > 2:
            i += 1; continue  # silent final e
        if s[i] == "e" and i + 1 < len(s) and i + 2 <= len(s) and s[i + 1:i + 3] in ("r", " ", "-", ""):
            pass
        if s[i] in "ei" and i + 2 < len(s) and s[i + 1] in ("n", "r") and i + 2 == len(s) - 0:
            pass  # keep simple
        if s[i] in "dg" and s[i + 1:i + 2] == "e":
            out.append("д"); i += 2; continue
        if s[i] == "t" and s[i + 1:i + 3] == "io":
            out.append("ш"); i += 2; continue
        if s[i] == "s" and s[i + 1:i + 3] == "io":
            out.append("ш"); i += 2; continue
        if s[i] == "c" and s[i + 1:i + 2] in ("e", "i", "y"):
            out.append("с"); i += 1; continue
        if s[i] == "g" and s[i + 1:i + 2] in ("e", "i", "y"):
            out.append("дж"); i += 1; continue
        out.append(pairs_single.get(s[i], s[i]))
        i += 1
    r = "".join(out)
    return r[:1].upper() + r[1:] if w[:1].isupper() else r


def translit(text: str) -> str:
    toks = text.split()
    out = []
    for t in toks:
        if t.casefold() in SKIP_WORDS:
            out.append(t)
            continue
        bare = t.strip("-")
        core = translit_word(bare) if bare.isascii() and bare.isalpha() else t
        out.append(t.replace(bare, core) if bare != t else core)
    return " ".join(out)


def main():
    root = Path(__file__).resolve().parents[1]
    sample = {x["example_id"]: x for x in
              (json.loads(l) for l in (root / "samples" / "sample200.jsonl").open())}
    exp2 = [json.loads(l) for l in (root / "results" / "exp2_wikidata.jsonl").open()]
    exp3 = {r["example_id"]: r for r in
            (json.loads(l) for l in (root / "results" / "exp3_sources.jsonl").open())}

    rows = []
    for r in exp2:
        it = sample[r["example_id"]]
        t_ex = exp3.get(r["example_id"], {})
        tr = translit(r["source"])
        ref = r.get("ru_form") or ""
        rows.append({
            "example_id": r["example_id"], "type": r["candidate_type"],
            "source": r["source"], "translit": tr,
            "wd_ru": ref, "wd_ru_source": r.get("ru_source", ""),
            "score": r["score"], "flags": r["flags"],
        })
    # reference subset: confident identity + clean cyrillic RU form
    ref_rows = [x for x in rows
                if x["score"] >= 0.9
                and x["wd_ru"]
                and all(ord(c) >= 0x400 for c in x["wd_ru"] if c.isalpha())
                and "multiple plausible QIDs" not in x["flags"]
                and "disambiguation_page" not in x["flags"]]
    agree_exact = sum(1 for x in ref_rows if norm_key(x["translit"]) == norm_key(x["wd_ru"]))
    trad_agree = sum(1 for x in ref_rows
                     if norm_key(TRADITIONAL.get(x["source"].casefold(), x["translit"])) == norm_key(x["wd_ru"]))
    by_type = {}
    for t in sorted({x["type"] for x in ref_rows}):
        sub = [x for x in ref_rows if x["type"] == t]
        if not sub:
            continue
        a = sum(1 for x in sub if norm_key(x["translit"]) == norm_key(x["wd_ru"]))
        at = sum(1 for x in sub if norm_key(TRADITIONAL.get(x["source"].casefold(), x["translit"])) == norm_key(x["wd_ru"]))
        by_type[t] = {"n": len(sub), "translit_agree": a / len(sub),
                      "translit_plus_dict_agree": at / len(sub)}

    # mandatory cases through the rules
    mandatory_rule = {v: translit(v) for v in
                      ["Smith", "Smyth", "New York", "Arsenal", "Washington", "London", "George"]}
    mandatory_with_dict = {
        v: " ".join(TRADITIONAL.get(w.casefold(), translit(w)) for w in v.split())
        for v in ["Smith", "Smyth", "New York", "Arsenal", "Washington", "London", "George"]}
    stats = {
        "note": ("transliteration agreement is measured against Wikidata's conventional RU form "
                 "on the confident subset; it is NOT accuracy vs a gold standard"),
        "n_sample": len(rows),
        "n_reference_subset": len(ref_rows),
        "raw_translit_agreement": agree_exact / max(1, len(ref_rows)),
        "translit_plus_traditional_dict_agreement": trad_agree / max(1, len(ref_rows)),
        "agreement_by_type": by_type,
        "mandatory_cases_rule_only": mandatory_rule,
        "mandatory_cases_with_dict": mandatory_with_dict,
    }
    jdump(root / "results" / "exp4_translit_stats.json", stats)
    jdumpl(root / "results" / "exp4_translit.jsonl", rows)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
