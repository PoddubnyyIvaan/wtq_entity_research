"""Experiment 2 - Wikidata as entity resolver with context-based candidate ranking.

For each sampled cell:
 1. wbsearchentities (en) for the cell value -> candidate QIDs.
 2. Rank candidates by: string similarity to source (label/alias), P31 type
    compatibility with the column header, disambiguation-page penalty.
 3. For the best QID fetch en/ru label, ru aliases, ru sitelink title,
    P31 types, description.
 4. Produce a suggested Russian form in priority: ru sitelink title > ru label
    > ru alias > none.  Flag cases (latin RU, disambiguation, no form, ...).

All HTTP responses are cached on disk; 200ms rate limit between requests.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Http, jdump, jdumpl, norm_key

WD = "https://www.wikidata.org/w/api.php"

KNOWN_Q = {
    "Q5": "human", "Q6256": "country", "Q4167410": "disambiguation page",
    "Q515": "city", "Q486972": "human settlement", "Q43229": "organization",
    "Q476028": "sports team", "Q12973014": "sports team (assoc.)",
    "Q4762519": "association football match", "Q847017": "sports league",
    "Q13433827": "encyclopedia article", "Q17329259": "encyclopedia article",
    "Q11424": "film", "Q7725634": "literary work", "Q134556": "single",
    "Q482994": "album", "Q2743": "municipality of France",
}

HEADER_TYPES = {
    "country": "country", "nation": "country", "nationality": "country",
    "city": "city", "town": "city", "venue": "city", "location": "city",
    "team": "sports team", "club": "sports team", "opponent": "sports team",
    "winner": "sports team", "player": "human", "name": "human",
    "artist": "human", "director": "human", "driver": "human", "rider": "human",
    "album": "album", "film": "film", "movie": "film", "song": "single",
    "title": "album", "event": "sports competition", "tournament": "sports competition",
    "competition": "sports competition",
}


def sim(a: str, b: str) -> float:
    a, b = norm_key(a), norm_key(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / max(1, len(ta | tb))
    pre = 1.0 if b.startswith(a) or a.startswith(b) else 0.0
    return 0.7 * jac + 0.3 * pre


def main():
    root = Path(__file__).resolve().parents[1]
    items = [json.loads(l) for l in (root / "samples" / "sample200.jsonl").open()]
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(items)
    items = items[:limit]
    http = Http("wikidata", min_interval=0.55)

    results = []
    WP = "https://en.wikipedia.org/w/api.php"
    for i, it in enumerate(items):
        if i % 10 == 0:
            print(f"exp2: {i}/{len(items)} interval={http.min_interval:.2f}s", flush=True)
        value = it["cell_value"]
        clean = value.strip(" @*")
        clean = re.sub(r"\((?:[^()]|\([^()]*\))*\)", "", clean).strip(" @*-")  # annotations
        clean = re.sub(r"^(?:@\s*|#\d+\s*|\d+\s+)", "", clean).strip()
        if not clean:
            clean = value.strip(" @*")
        expected = HEADER_TYPES.get(norm_key(it["column_header"]).split("\n")[0], "")
        # 1) search
        s = http.get_json(f"{WD}?action=wbsearchentities&search={quote(clean)}&language=en&format=json&limit=8&type=item&origin=*")
        cands = [] if "__error__" in s else s.get("search", [])
        # 1b) fallback: Wikipedia full-text search -> linked Wikidata item
        if not cands and clean:
            ws = http.get_json(f"{WP}?action=query&format=json&list=search&srsearch={quote(clean)}&srlimit=5&sroffset=0")
            if "__error__" not in ws:
                titles = [h["title"] for h in ws.get("query", {}).get("search", [])][:5]
                if titles:
                    pp = http.get_json(f"{WP}?action=query&format=json&prop=pageprops&ppprop=wikibase_item&titles={'|'.join(quote(t) for t in titles)}&redirects=1")
                    qids_w = [v.get("pageprops", {}).get("wikibase_item", "")
                              for v in (pp.get("query", {}).get("pages", {}) or {}).values()]
                    qids_w = [q for q in qids_w if q][:8]
                    if qids_w:
                        g0 = http.get_json(f"{WD}?action=wbgetentities&ids={'|'.join(qids_w)}&props=labels&languages=en&format=json&origin=*")
                        for q, lab in ((q, (g0.get("entities", {}) or {}).get(q, {}).get("labels", {}).get("en", {}).get("value", ""))
                                       for q in qids_w):
                            cands.append({"id": q, "label": lab, "match": {"type": "label"}})
        qids = [c["id"] for c in cands][:8]
        # 2) fetch details for candidates (batched)
        det = {}
        if qids:
            g = http.get_json(f"{WD}?action=wbgetentities&ids={'|'.join(qids)}&props=labels|aliases|sitelinks|descriptions|claims&languages=en|ru&sitefilter=enwiki|ruwiki&format=json&origin=*")
            det = {} if "__error__" in g else g.get("entities", {})
        scored = []
        for c in cands:
            q = det.get(c["id"], {})
            labels = {k: v["value"] for k, v in (q.get("labels") or {}).items()}
            aliases = {k: [a["value"] for a in v] for k, v in (q.get("aliases") or {}).items()}
            sitelinks = {k: v["title"] for k, v in (q.get("sitelinks") or {}).items()}
            p31 = [KNOWN_Q.get(st["mainsnak"]["datavalue"]["value"]["id"],
                               st["mainsnak"]["datavalue"]["value"]["id"])
                   for st in (q.get("claims", {}).get("P31") or [])
                   if "datavalue" in st.get("mainsnak", {})]
            best_label = max([labels.get("en", "")] + aliases.get("en", []),
                             key=lambda x: sim(clean, x), default="")
            sc = sim(clean, best_label)
            if "disambiguation page" in p31:
                sc -= 0.4
            if expected and any(expected in t for t in p31):
                sc += 0.15
            if c.get("match", {}).get("type") == "label":
                sc += 0.05
            scored.append({"qid": c["id"], "en_label": labels.get("en", ""),
                           "en_desc": (q.get("descriptions", {}).get("en", {}) or {}).get("value", ""),
                           "p31": p31[:6], "score": round(sc, 3),
                           "ru_label": labels.get("ru", ""),
                           "ru_aliases": aliases.get("ru", [])[:5],
                           "ru_sitelink": sitelinks.get("ruwiki", ""),
                           "en_sitelink": sitelinks.get("enwiki", "")})
        scored.sort(key=lambda x: -x["score"])
        top = scored[0] if scored else None
        flags = []
        ru_form, ru_source = "", ""
        if not cands:
            flags.append("no_candidates")
        elif top is None:
            flags.append("no_rankable_candidate")
        else:
            if "disambiguation page" in (top["p31"] or []):
                flags.append("disambiguation_page")
            ru_form, ru_source = pick_ru(top)
            if not ru_form:
                flags.append("RU form missing")
            elif is_latin(ru_form):
                flags.append("RU form is Latin")
            if len(scored) > 1 and scored[1]["score"] >= top["score"] - 0.05 and top["score"] >= 0.8:
                flags.append("multiple plausible QIDs")
            if top["score"] < 0.6:
                flags.append("low string match")
        results.append({
            "example_id": it["example_id"], "candidate_type": it["candidate_type"],
            "source": value, "column_header": it["column_header"],
            "qid": top["qid"] if top else "", "en_label": top["en_label"] if top else "",
            "en_desc": top["en_desc"] if top else "",
            "ru_form": ru_form, "ru_source": ru_source,
            "score": top["score"] if top else 0.0,
            "runners_up": [(x["qid"], x["score"]) for x in scored[1:3]],
            "flags": flags, "expected_type": expected,
        })
    suffix = "_pilot" if limit < 200 else ""
    jdump(root / "results" / f"exp2_wikidata{suffix}_stats.json", aggregate(results))
    jdumpl(root / "results" / f"exp2_wikidata{suffix}.jsonl", results)
    print("exp2 done:", aggregate(results), flush=True)


def pick_ru(top):
    if top["ru_sitelink"]:
        return top["ru_sitelink"], "ru_sitelink"
    if top["ru_label"] and not is_latin(top["ru_label"]):
        return top["ru_label"], "ru_label"
    for a in top["ru_aliases"]:
        if not is_latin(a):
            return a, "ru_alias"
    if top["ru_label"]:
        return top["ru_label"], "ru_label_latin"
    return "", ""


def is_latin(s: str) -> bool:
    return bool(s) and all(ord(ch) < 0x400 for ch in s if ch.isalpha())


def aggregate(results):
    n = len(results)
    flags = [f for r in results for f in r["flags"]]
    from collections import Counter
    return {
        "n": n,
        "candidate_coverage": sum(1 for r in results if r["qid"]) / n,
        "russian_form_coverage": sum(1 for r in results if r["ru_form"]) / n,
        "ru_source_dist": dict(Counter(r["ru_source"] for r in results)),
        "flag_distribution": dict(Counter(flags)),
        "score_mean": sum(r["score"] for r in results) / n,
        "score_ge_0.8": sum(1 for r in results if r["score"] >= 0.8) / n,
    }


def quote(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s)


if __name__ == "__main__":
    main()
