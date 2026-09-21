"""Build the stratified 200-candidate sample from existing CoreNLP tagging."""
from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import WTQ, jdump, jdumpl, unescape_wtq

SEED = 42

QUOTAS = {
    "PERSON": 30, "SURNAME": 15, "LOCATION": 25, "ORGANIZATION": 20,
    "SPORTS_TEAM": 20, "EVENT_WORK": 25, "MULTI_WORD": 20,
    "SHORT_AMBIGUOUS": 20, "FALSE_POSITIVE": 15, "UNKNOWN": 10,
}

SPORTS_HEADERS = {
    "opponent", "team", "club", "winner", "home team", "away team", "visiting team",
    "opposition", "losing pitcher", "winning pitcher", "away", "home", "rival",
    "champion", "runner-up", "second place", "third place", "final opponent",
}
WORK_HEADERS = {
    "album", "film", "song", "title", "movie", "show", "series", "event", "tournament",
    "competition", "episode", "game", "book", "single", "label", "track", "director",
    "producer", "work", "story", "video game", "television series", "movie/series",
}
FIRST_NAMES = set("""john james robert michael william david richard joseph thomas charles
george henry edward frank peter jack alex harry max oscar carl louis victor hugo felix
anna maria sara elena julia laura anna kate mary linda patricia jennifer elizabeth susan
margaret dorothy helen sandra nancy karen betty ruth sharon michelle carol amanda melissa
deborah stephanie rebecca sharon cynthia kathleen amy angela shirley brenda pamela emma
pia mia lena ina ira eve amy kim jane jean june joan ann sue may ivy ola una eva ida
lia ria nia tia pia sofia clara cora nora flora dora lora Mara Lior""".split())

STOPWORDS_FALSE = set("""total none score result notes rank number date year time season place
round week no type name record position points total wins losses ties draws percentage
attendance opposition venue status style format length size height weight diameter mass
capacity length width depth population area density elevation climate temperature rainfall
seasons class category group section unit part level stage phase period era age sex gender
race ethnicity language religion nationality occupation job title role title status rank
grade score mark rating average median mode sum difference product ratio fraction percent
total count index code id key type kind sort order sequence series set collection batch
lot piece item article product commodity good service benefit cost price value worth fee
charge bill account payment deposit credit debit balance interest rate yield return profit
gain loss revenue income earnings salary wage pay compensation bonus reward prize award
medal trophy cup title crown belt championship tournament competition match game race
event contest quiz test exam trial audition interview meeting conference summit session
""".split())


def is_number(s: str) -> bool:
    try:
        float(s.replace(",", "").replace("%", "").strip())
        return True
    except ValueError:
        return False


def is_pct(s):
    return bool(re.fullmatch(r"[+-]?\d[\d,.\s]*\s*%", s.strip()))


def is_date_like(s: str) -> bool:
    s = s.strip()
    if re.fullmatch(r"\d{4}(-\d{1,2}(-\d{1,2})?)?", s):
        return True
    if re.search(r"\b(19|20)\d{2}\b", s) and len(s) < 30:
        return True
    return bool(re.fullmatch(r"[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+(19|20)\d{2}", s))


def load_metadata():
    meta = {}
    with (WTQ / "misc" / "table-metadata.tsv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            meta[r["contextId"]] = r
    return meta


def load_questions():
    qmap = defaultdict(list)  # context path -> [(id, utterance)]
    with (WTQ / "data" / "training.tsv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            qmap[r["context"]].append((r["id"], r["utterance"]))
    return qmap


def stratum_of(cell: dict, header: str, tags: set) -> str:
    h = header.strip().casefold()
    value = cell["content"]
    toks = value.split()
    capitalized_words = [t for t in toks if t[:1].isupper() or t[:1].isdigit() is False and t[:1].isalpha()]
    if "PERSON" in tags and "LOCATION" not in tags and "ORGANIZATION" not in tags:
        if len(toks) == 1 and value.casefold() not in FIRST_NAMES:
            return "SURNAME"
        return "PERSON"
    if "LOCATION" in tags:
        return "LOCATION"
    if "ORGANIZATION" in tags:
        if h in SPORTS_HEADERS:
            return "SPORTS_TEAM"
        return "ORGANIZATION"
    if "MISC" in tags:
        return "EVENT_WORK" if h in WORK_HEADERS else "UNKNOWN"
    # no NER tags at all
    if value.casefold() in {"n/a", "na", "tbd", "tba", "none", "unknown", "—", "-", "–"}:
        return "FALSE_POSITIVE"
    if sum(ch.isdigit() for ch in value) >= 2 and len(toks) == 1:
        return "FALSE_POSITIVE"  # code-like immutable ("728i", "8th")
    if len(toks) > 1 and any(t[:1].isupper() for t in toks[1:]) and sum(ch.isdigit() for ch in value) <= 1:
        return "MULTI_WORD"
    if len(toks) == 1 and value[:1].isupper() and value.casefold() not in FIRST_NAMES \
            and value.casefold() not in STOPWORDS_FALSE and value[1:2].islower():
        return "SHORT_AMBIGUOUS"
    if value.casefold() in STOPWORDS_FALSE or (len(toks) == 1 and value.islower() and len(value) >= 3):
        return "FALSE_POSITIVE"
    return "UNKNOWN"


def main():
    rng = random.Random(SEED)
    meta = load_metadata()
    qmap = load_questions()
    # build pools
    pools = defaultdict(list)
    pool_stats = Counter()
    seen_cells = set()
    for td in sorted((WTQ / "tagged").glob("*-tagged")):
        n = td.name.replace("-tagged", "")
        for p in td.glob("*.tagged"):
            m = p.stem
            table_id = f"{n}/{m}"
            ctx_path = f"csv/{n}-csv/{m}.csv"
            headers = {}
            rows_cells = defaultdict(dict)
            ner_by_cell = defaultdict(set)
            with p.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    r, c = int(row["row"]), int(row["col"])
                    if r == -1:
                        headers[c] = row["content"].replace("\n", " ").strip()
                    else:
                        rows_cells[r][c] = unescape_wtq(row["content"])
                        for t in (row["nerTags"] or "").split("|"):
                            if t and t != "O":
                                ner_by_cell[c].add(t)
            mrows = meta.get(ctx_path, {})
            qs = qmap.get(ctx_path, [])
            for r, cols in rows_cells.items():
                row_context = {str(c): v[:50] for c, v in sorted(cols.items())[:10]}
                for c, v in cols.items():
                    v = v.strip()
                    key = (table_id, r, c)
                    if key in seen_cells or not v or len(v) > 60 or is_number(v) or is_pct(v) or is_date_like(v):
                        continue
                    if "\n" in v or not any(ch.isalpha() for ch in v) or len(v) < 3:
                        continue
                    if any(not ch.isascii() and ch.isalpha() and ch not in "éèêëáàâäíìîïóòôöúùûüçñåøæœšžý" for ch in v):
                        continue  # skip non-Latin scripts, recorded as known limitation
                    seen_cells.add(key)
                    st = stratum_of({"content": v}, headers.get(c, ""), ner_by_cell[c])
                    pool_stats[st] += 1
                    # prefer questions containing the value
                    qsel = [(qid, u) for qid, u in qs if v.casefold() in u.casefold()] or qs
                    qid, utt = (qsel[0] if qsel else ("", ""))
                    pools[st].append({
                        "table_id": table_id,
                        "question_id": qid,
                        "cell_value": v,
                        "column_header": headers.get(c, ""),
                        "row_context": row_context,
                        "table_caption_or_title": (mrows.get("caption") or mrows.get("title") or "")[:120],
                        "page_title": mrows.get("title", ""),
                        "page_url": mrows.get("url", "") if False else "",
                        "table_index": mrows.get("tableIndex", ""),
                        "question_context": utt[:200],
                        "candidate_type": st,
                        "source_location": f"row={r},col={c}",
                        "ner_tags": sorted(ner_by_cell[c]),
                    })

    # fill page_url separately from page json (only for sampled items, keep IO low)
    sample = []
    for st, quota in QUOTAS.items():
        pool = pools[st]
        rng.shuffle(pool)
        # prefer items that have a question for richer context, but keep mix
        withq = [x for x in pool if x["question_id"]]
        noq = [x for x in pool if not x["question_id"]]
        take = withq[: int(quota * 0.8)] + noq[: quota]
        take = take[:quota]
        for i, item in enumerate(take):
            item["example_id"] = f"e{len(sample) + 1:03d}"
            sample.append(item)
    rng.shuffle(sample)
    for i, item in enumerate(sample):
        item["example_id"] = f"e{i + 1:03d}"
        try:
            pj = json.loads((WTQ / "page" / f"{item['table_id'].split('/')[0]}-page" /
                             f"{item['table_id'].split('/')[1]}.json").read_text(encoding="utf-8"))
            item["page_url"] = pj.get("url", "")
        except Exception:
            item["page_url"] = ""

    dev_n = 20
    for i, item in enumerate(sample):
        item["subset"] = "dev" if i < dev_n else "eval"
    jdump(Path(__file__).resolve().parents[1] / "samples" / "pool_stats.json",
          {"pool_counts_per_stratum": dict(pool_stats), "quotas": QUOTAS})
    jdumpl(Path(__file__).resolve().parents[1] / "samples" / "sample200.jsonl", sample)
    jdump(Path(__file__).resolve().parents[1] / "samples" / "mandatory_cases.json", [
        {"value": v, "note": "mandatory synthetic case"} for v in
        ["Smith", "Smyth", "New York", "Arsenal", "Washington", "London", "George"]])
    print("pool sizes:", dict(pool_stats))
    print("sampled:", Counter(x["candidate_type"] for x in sample))
    print("dev/eval:", Counter(x["subset"] for x in sample))
    print("with question:", sum(1 for x in sample if x["question_id"]))


if __name__ == "__main__":
    main()
