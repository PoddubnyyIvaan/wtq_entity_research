"""Convert samples/entities.tsv (TSV) into samples/sample200.jsonl (JSONL).

Маппинг 1 строка TSV -> 1 объект JSONL со строго 15 ключами из канонического
sample200.jsonl. Парсинг TSV — построчный split("\\t") БЕЗ CSV-quoting: в поле
name могут встречаться двойные кавычки как часть surface form, и csv.DictReader
теряет на них строки. Поле count из TSV в выход не включается (решение
пользователя). Спецификация: specs/entities_to_sample200.md.

CLI: python3 scripts/entities_to_sample200.py [INPUT_TSV] [OUTPUT_JSONL]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

INPUT_DEFAULT = Path(__file__).resolve().parents[1] / "samples" / "entities.tsv"
OUTPUT_DEFAULT = Path(__file__).resolve().parents[1] / "samples" / "sample200.jsonl"

EXPECTED_HEADER = ["name", "type", "count", "all_types"]

# Порядок ключей в точности как в samples/sample200.jsonl
SAMPLE_KEYS = [
    "table_id", "question_id", "cell_value", "column_header", "row_context",
    "table_caption_or_title", "page_title", "page_url", "table_index",
    "question_context", "candidate_type", "source_location", "ner_tags",
    "example_id", "subset",
]


def read_spec_rows(path: Path) -> list[dict]:
    """Читает TSV как набор (name, type, count, all_types), сохраняя кавычки."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        raise ValueError("входной файл пуст")
    header = lines[0].split("\t")
    if header != EXPECTED_HEADER:
        raise ValueError(f"неожиданный заголовок: {header!r}, ожидалось {EXPECTED_HEADER!r}")
    rows: list[dict] = []
    for lineno, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue  # пустая физическая строка — допустима
        fields = line.split("\t")
        if len(fields) != 4:
            raise ValueError(
                f"строка {lineno}: ожидалось 4 поля, получено {len(fields)}"
            )
        name, ctype, count, all_types = fields
        if not name.strip():
            raise ValueError(f"строка {lineno}: пустое поле name")
        rows.append({
            "name": name,
            "type": ctype,
            "count": count,
            "all_types": all_types,
        })
    return rows


def to_sample_row(index: int, total: int, row: dict) -> dict:
    """Строит объект формата sample200.jsonl из строки TSV."""
    width = max(3, len(str(total)))
    ner_tags = sorted(
        t for t in (row["all_types"].split("|") if row["all_types"] else []) if t
    )
    subset = "dev" if index < 20 else "eval"
    item = {
        "table_id": "",
        "question_id": "",
        "cell_value": row["name"],
        "column_header": "",
        "row_context": {},
        "table_caption_or_title": "",
        "page_title": "",
        "page_url": "",
        "table_index": "",
        "question_context": "",
        "candidate_type": row["type"],
        "source_location": "",
        "ner_tags": ner_tags,
        "example_id": f"e{index + 1:0{width}d}",
        "subset": subset,
    }
    assert list(item) == SAMPLE_KEYS, "нарушен порядок ключей формата sample200"
    return item


def main() -> int:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_DEFAULT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_DEFAULT

    try:
        rows = read_spec_rows(input_path)
    except FileNotFoundError:
        print(f"ошибка: входной файл не найден: {input_path}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1

    total = len(rows)
    out_lines = [json.dumps(to_sample_row(i, total, r), ensure_ascii=False)
                 for i, r in enumerate(rows)]
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"ошибка записи: {exc}", file=sys.stderr)
        return 1

    # сводка
    from collections import Counter
    subset_counts = Counter(
        s for s in (json.loads(ln)["subset"] for ln in out_lines)
    )
    print(f"converted {total} rows -> {output_path}")
    print(f"example_id: {json.loads(out_lines[0])['example_id']} .. "
          f"{json.loads(out_lines[-1])['example_id']}")
    print("subset dist:", dict(subset_counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())