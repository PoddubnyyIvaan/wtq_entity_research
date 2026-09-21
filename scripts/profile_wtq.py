"""Profile WikiTableQuestions by streaming all main files. Writes JSON stats."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import WTQ, read_tagged_data, jdump, table_id_from_context

RE = sys.stdout.reconfigure  # noqa


def is_number(s: str) -> bool:
    try:
        float(s.replace(",", "").replace("%", "").strip())
        return True
    except ValueError:
        return False


def is_date_like(s: str) -> bool:
    s = s.strip()
    if re.fullmatch(r"\d{4}(-\d{1,2}(-\d{1,2})?)?", s):
        return True
    if re.search(r"\b(19|20)\d{2}\b", s) and len(s) < 30 and not is_number(s.replace(",", "")):
        return True
    return bool(re.fullmatch(r"[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+(19|20)\d{2}", s))


def is_pct(s: str) -> bool:
    return bool(re.fullmatch(r"[+-]?\d[\d,.\s]*\s*%", s.strip()))


def is_cyrillic(s: str) -> bool:
    return any("CYRILLIC" in unicodedata.name(ch, "") for ch in s)


def main():
    stats = {
        "questions": Counter(),          # per split
        "tables": set(),                 # unique context paths (training + pristine)
        "tagged_cells": 0,
        "tagged_files": 0,
        "cell_values": Counter(),        # unique cell strings
        "cell_col_by_value": defaultdict(Counter),  # value -> column names seen
        "value_len_hist": Counter(),
        "cls": Counter(),
        "header_freq": Counter(),
        "ner_tagged_token_types": Counter(),
        "cyrillic_cells": 0,
    }
    ner_token_total = 0

    # ---- tables: unique contexts from data/*.tsv (streaming)
    for split in ["training", "pristine-unseen-tables", "pristine-seen-tables"]:
        p = WTQ / "data" / f"{split}.tsv"
        with p.open(encoding="utf-8", newline="") as f:
            reader = __import__("csv").DictReader(f, delimiter="\t")
            n = 0
            for row in reader:
                n += 1
                stats["tables"].add(row["context"])
        stats["questions"][split] = n

    # ---- per-table cell stats via tagged/<N>-tagged/<M>.tagged
    tdirs = sorted((WTQ / "tagged").glob("*-tagged"))
    rows_per_table = Counter()
    cols_per_table = Counter()
    cells_per_table = Counter()
    for td in tdirs:
        stats["tagged_files"] += len(list(td.glob("*.tagged")))
        for p in td.glob("*.tagged"):
            nrows = 0
            ncols = 0
            ncell = 0
            with p.open(encoding="utf-8", newline="") as f:
                reader = __import__("csv").DictReader(f, delimiter="\t")
                for row in reader:
                    ncell += 1
                    stats["tagged_cells"] += 1
                    content = row["content"]
                    if int(row["row"]) == -1:
                        ncols += 1
                        hdr = content.replace("\n", " ").strip()
                        stats["header_freq"][hdr] += 1
                        continue
                    nrows = max(nrows, int(row["row"]) + 1)
                    v = content.strip()
                    if not v:
                        cls = "empty"
                    elif is_number(v.replace(",", "")):
                        cls = "pct" if is_pct(v) else "number"
                    elif is_date_like(v):
                        cls = "date"
                    else:
                        cls = "other"
                        if is_cyrillic(v):
                            cls = "other_cyrillic"
                            stats["cyrillic_cells"] += 1
                    stats["cls"][cls] += 1
                    if cls in ("other", "other_cyrillic") and 0 < len(v) < 60:
                        stats["cell_values"][v] += 1
                        stats["value_len_hist"][min(len(v) // 10 * 10, 60)] += 1
                rows_per_table[table_id_from_context(f"csv/{td.name.replace('-tagged','')}-csv/{p.stem}.csv")] = nrows
                cols_per_table[p.stem] = ncols
                cells_per_table[p.stem] = ncell

    # ---- NER tag distribution in cell tags (subsample: every 20th tagged file)
    tag_counter = Counter()
    files = sorted((WTQ / "tagged").glob("*-tagged/*.tagged"))[::20]
    for p in files:
        with p.open(encoding="utf-8", newline="") as f:
            for row in __import__("csv").DictReader(f, delimiter="\t"):
                for t in row["nerTags"].split("|"):
                    if t and t != "O":
                        tag_counter[t] += 1
                    ner_token_total += 1
    stats["ner_cell_tags"] = tag_counter
    stats["ner_tokens_sampled"] = ner_token_total

    tables = stats.pop("tables")
    out = {
        "questions_per_split": dict(stats["questions"]),
        "unique_tables_in_splits": len(tables),
        "tagged_table_files": stats["tagged_files"],
        "tagged_cells_total": stats["tagged_cells"],
        "rows_per_table": {
            "min": min(rows_per_table.values()), "max": max(rows_per_table.values()),
            "mean": sum(rows_per_table.values()) / len(rows_per_table),
            "tables_with_rows_ge_2": sum(1 for v in rows_per_table.values() if v >= 2),
        },
        "cols_per_table": {
            "min": min(cols_per_table.values()), "max": max(cols_per_table.values()),
            "mean": sum(cols_per_table.values()) / len(cols_per_table),
        },
        "cell_class_counts": dict(stats["cls"]),
        "cyrillic_in_cells": stats["cyrillic_cells"],
        "value_len_hist_deciles": {str(k): v for k, v in sorted(stats["value_len_hist"].items())},
        "unique_string_values_lt60chars": len(stats["cell_values"]),
        "string_cells_lt60chars": sum(stats["cell_values"].values()),
        "repeat_rate_across_tables": (
            sum(1 for v, c in stats["cell_values"].items() if c > 1) / len(stats["cell_values"])
        ),
        "ner_cell_tags_top25": dict(tag_counter.most_common(25)),
        "ner_tokens_sampled": ner_token_total,
        "top50_headers": dict(stats["header_freq"].most_common(50)),
    }
    jdump(Path(__file__).resolve().parents[1] / "data_profile" / "wtq_profile.json", out)
    print(json.dumps({k: v for k, v in out.items() if k not in ("top50_headers",)}, ensure_ascii=False, indent=1)[:4000])
    print("TOP50 HEADERS:", out["top50_headers"])


if __name__ == "__main__":
    main()
