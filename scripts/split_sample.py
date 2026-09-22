"""Split samples/sample200.jsonl into N equal contiguous JSONL parts.

Каждая запись — одна физическая строка. Части — непрерывные непересекающиеся
срезы исходного файла; размеры отличаются не более чем на 1 строку. Строки
копируются байт-в-байт (без пересоздания JSON), порядок и example_id внутри
части не меняются. Выход: <stem>_part1..K<suffix> рядом с входом.

CLI: python3 scripts/split_sample.py [INPUT_JSONL] [N_PARTS]
Спецификация: specs/split_sample.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

INPUT_DEFAULT = Path(__file__).resolve().parents[1] / "samples" / "sample200.jsonl"
PARTS_DEFAULT = 6


def part_sizes(total: int, parts: int) -> list[int]:
    """Равные по возможности размеры частей: сумма = total, |разность| <= 1.

    total = base*parts + rem  ->  первые rem частей получают base+1 строк.
    """
    base, rem = divmod(total, parts)
    return [base + 1] * rem + [base] * (parts - rem)


def example_id(line: str) -> str:
    """example_id строки для сводки; пустая строка при битом JSON."""
    try:
        return json.loads(line)["example_id"]
    except (json.JSONDecodeError, KeyError):
        return "<n/a>"


def split_file(
    input_path: Path, parts: int
) -> list[tuple[Path, int, str, str]]:  # (путь, строк, первый example_id, последний)
    """Разрезает input_path на `parts` частей; возвращает (путь, строк) списком."""
    if not input_path.exists():
        raise FileNotFoundError(f"входной файл не найден: {input_path}")
    n = sum(1 for _ in input_path.open(encoding="utf-8"))
    if n == 0:
        raise ValueError(f"входной файл пуст: {input_path}")
    if parts < 1 or parts > n:
        raise ValueError(f"N_PARTS должно быть 1..{n}, получено {parts}")
    sizes = part_sizes(n, parts)

    out_dir = input_path.parent
    out_paths = [out_dir / f"{input_path.stem}_part{i + 1}{input_path.suffix}"
                 for i in range(parts)]
    handles = [p.open("w", encoding="utf-8") for p in out_paths]
    first_id: list[str] = [""] * parts
    last_id: list[str] = [""] * parts
    written = [0] * parts
    try:
        cur = 0
        remaining = sizes[0]
        with input_path.open(encoding="utf-8") as f:
            for line in f:
                handles[cur].write(line)
                if remaining == sizes[cur]:
                    first_id[cur] = example_id(line)
                last_id[cur] = example_id(line)
                written[cur] += 1
                remaining -= 1
                if remaining == 0 and cur + 1 < parts:
                    cur += 1
                    remaining = sizes[cur]
    finally:
        for h in handles:
            h.close()
    if written != sizes:
        raise RuntimeError(
            f"контроль размеров не сошёлся: записано {written}, ожидалось {sizes}"
        )
    return [(p, n_rows, f, l) for p, n_rows, f, l in
            zip(out_paths, written, first_id, last_id)]


def main() -> int:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_DEFAULT
    try:
        parts = int(sys.argv[2]) if len(sys.argv) > 2 else PARTS_DEFAULT
    except ValueError:
        print(f"ошибка: N_PARTS не число: {sys.argv[2]!r}", file=sys.stderr)
        return 1
    try:
        summary = split_file(input_path, parts)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, FileNotFoundError) else 1
    for path, rows, f, l in summary:
        print(f"{path}: {rows} строк, example_id {f} .. {l}")
    total = sum(r for _, r, _, _ in summary)
    print(f"split {total} строк -> {len(summary)} частей")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())