"""Experiment 3 - Wikipedia langlinks vs Wikidata sitelink/label/alias RU forms.

For every cell where Experiment 2 found a QID, fetch the RU form from:
  A) Wikidata ru sitelink title  (cached from exp2)
  B) Wikidata ru label           (cached from exp2)
  C) Wikidata ru aliases         (cached from exp2)
  D) English Wikipedia langlinks API (independent fetch)

Compare coverage and agreement between sources; count disambiguation-style
titles like "(значения)", Latin-script forms, and cases where one source is
useful while another is not.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Http, jdump, jdumpl, norm_key

WP = "https://en.wikipedia.org/w/api.php"
DIS_NOISE = re.compile(r"\((?:значения|значение|футбол[^\)]*|клуб|команда|город)\)$|\(.*\)$", re.I)


def is_latin(s: str) -> bool:
    return bool(s) and all(ord(ch) < 0x400 for ch in s if ch.isalpha())


def classify_ru(s: str):
    if not s:
        return "missing"
    if is_latin(s):
        return "latin"
    if DIS_NOISE.search(s):
        return "disambig_style"
    return "cyrillic_clean"


def main():
    root = Path(__file__).resolve().parents[1]
    exp2 = [json.loads(l) for l in (root / "results" / "exp2_wikidata.jsonl").open()]
    # reload exp2 details (sitelinks/aliases) from cache by re-fetching details
    from common import RESEARCH  # noqa
    # Build per-QID info from the exp2 raw fetch: we need run exp2 again logic-lite:
    # reuse exp2 jsonl for ru_form/ru_source and score; fetch langlinks + aliases via API now.
    http = Http("wikipedia", min_interval=0.55)

    rows = []
    linked = [r for r in exp2 if r["qid"]]
    for r in linked:
        rows.append({
            "example_id": r["example_id"], "qid": r["qid"],
            "source_value": r["source"],
            "score": r["score"],
            "flags_exp2": r["flags"],
        })

    # merge with exp2 details: need ru sitelink/label/alias per qid -> re-extract from exp2 raw
    # re-open exp2 script's data path: details were fetched per item; salvage from cache
    cache = json.loads((root / "cache" / "wikidata_wd.json").read_text()) if (root / "cache" / "wikidata_wd.json").exists() else {}
    # exp2 stored details in its own per-item flow; recover by re-fetching wbgetentities for linked qids (batched 50)
    WD = "https://www.wikidata.org/w/api.php"
    qids = sorted({r["qid"] for r in linked})
    wdinfo = {}
    for k in range(0, len(qids), 50):
        batch = qids[k:k + 50]
        g = http.get_json(f"{WD}?action=wbgetentities&ids={'|'.join(batch)}&props=labels|aliases|sitelinks&languages=en|ru&sitefilter=enwiki|ruwiki&format=json&origin=*")
        if "__error__" in g:
            continue
        for q, v in g.get("entities", {}).items():
            labels = {kk: vv["value"] for kk, vv in (v.get("labels") or {}).items()}
            aliases = [a["value"] for a in (v.get("aliases") or {}).get("ru", [])]
            sitelinks = {kk: vv["title"] for kk, vv in (v.get("sitelinks") or {}).items()}
            wdinfo[q] = {
                "ru_sitelink": sitelinks.get("ruwiki", ""),
                "ru_label": labels.get("ru", ""),
                "ru_aliases": aliases[:6],
                "en_label": labels.get("en", ""),
                "en_sitelink": sitelinks.get("enwiki", ""),
            }
    # langlinks via en wiki, using en sitelink title from wdinfo
    for i, r in enumerate(rows):
        if i % 20 == 0:
            print(f"exp3 langlinks: {i}/{len(rows)}", flush=True)
        en_title = wdinfo.get(r["qid"], {}).get("en_sitelink", "")
        if en_title:
            u = (f"{WP}?action=query&format=json&formatversion=2&prop=langlinks&lllang=ru"
                 f"&titles={urllib.parse.quote(en_title)}&redirects=1")
            jj = http.get_json(u)
            pages = (jj.get("query") or {}).get("pages") or []
            if pages and "__error__" not in jj:
                r["wiki_langlinks_ru"] = (pages[0].get("langlinks") or [{}])[0].get("title", "")
        r.setdefault("wiki_langlinks_ru", "")
    for r in rows:
        info = wdinfo.get(r["qid"], {})
        r.update({
            "wd_ru_sitelink": info.get("ru_sitelink", ""),
            "wd_ru_label": info.get("ru_label", ""),
            "wd_ru_aliases": info.get("ru_aliases", []),
        })
        cls = {k: classify_ru(v) for k, v in [
            ("langlinks", r["wiki_langlinks_ru"]),
            ("sitelink", r["wd_ru_sitelink"]),
            ("label", r["wd_ru_label"]),
            ("alias", r["wd_ru_aliases"][0] if r["wd_ru_aliases"] else ""),
        ]}
        r["class_per_source"] = cls

    # agreement analysis
    n = len(rows)
    cov = {k: sum(1 for r in rows if r[k]) / n for k in
           ["wiki_langlinks_ru", "wd_ru_sitelink", "wd_ru_label"]}
    alias_cov = sum(1 for r in rows if r["wd_ru_aliases"]) / n
    agree = {
        "langlinks_vs_sitelink": sum(1 for r in rows if r["wiki_langlinks_ru"] and
                                     norm_key(r["wiki_langlinks_ru"]) == norm_key(r["wd_ru_sitelink"])) /
        max(1, sum(1 for r in rows if r["wiki_langlinks_ru"] and r["wd_ru_sitelink"])),
        "langlinks_vs_label": sum(1 for r in rows if r["wiki_langlinks_ru"] and
                                  norm_key(r["wiki_langlinks_ru"]) == norm_key(r["wd_ru_label"])) /
        max(1, sum(1 for r in rows if r["wiki_langlinks_ru"] and r["wd_ru_label"])),
    }
    stats = {
        "n_qid_linked": n,
        "coverage": cov,
        "alias_coverage": alias_cov,
        "agreement": agree,
        "class_dist_per_source": {
            s: {
                c: sum(1 for r in rows if r["class_per_source"][s] == c)
                for c in ("cyrillic_clean", "latin", "disambig_style", "missing")
            } for s in ("langlinks", "sitelink", "label", "alias")
        },
        "sitelink_better_than_label": (
            sum(1 for r in rows if classify_ru(r["wd_ru_sitelink"]) == "cyrillic_clean"
                and classify_ru(r["wd_ru_label"]) != "cyrillic_clean")),
        "alias_needed": (
            sum(1 for r in rows if classify_ru(r["wd_ru_sitelink"]) == "missing"
                and classify_ru(r["wd_ru_label"]) == "missing"
                and classify_ru(r["wd_ru_aliases"][0] if r["wd_ru_aliases"] else "") == "cyrillic_clean")),
        "langlinks_only": sum(1 for r in rows if r["wiki_langlinks_ru"]
                              and classify_ru(r["wd_ru_label"]) in ("missing", "latin")
                              and classify_ru(r["wd_ru_sitelink"]) in ("missing", "latin")),
    }
    jdump(root / "results" / "exp3_sources_stats.json", stats)
    jdumpl(root / "results" / "exp3_sources.jsonl", rows)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
