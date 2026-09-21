# REPORT — Эксперимент 2: Wiktionary EN→RU (Buchmeier DSL)

## Dataset

Wiktionary-derived DSL (Matthias Buchmeier), ~261 000 строк DSL (UTF-16 .dz),
наш индекс: 1 261 ключей EN → 5 235 RU-кандидатов с POS + sense.
Словарь сознательно маленький, но качественный по sense-структуре.

## Sample

`sample_200.jsonl` — тот же n=200 (seed 42).

## Lookup metrics (dictionary-only)

| Метрика | Значение |
|---|---|
| matched | **41 / 200 (20.5%)** |
| no_match | 159 (79.5%) |
| single / multiple | 11 / 30 |
| matched COMMON_WORD | 21 / 48 (44%) |
| matched NAMED_ENTITY | 19 / 121 (16%) |
| matched JUNK | 1 / 24 |
| matched UNKNOWN | 0 / 7 |

## Multiple senses (сохранены)

| Слово | Кандидаты (ru, POS) |
|---|---|
| current | нынешний(adj), текущий(adj), современный(m), поток(m), течение(m) |
| bank | отмель(f), банка(f), банк(m), берег(m) |
| book | книга(f), книжка(f), альбом(m), бронировать(impf), забронировать(impf) |
| record | запись(f), рекорд(m), пластинка(f), граммофонная пластинка(f) |
| field | область(f), отрасль(f), поле(n), луг(n), нива(n) |
| match | ровня, пара, спичка, матч, совпадать, совпасть |
| round | круглый, округлый, полный, закруглённый |
| Smith | кузнец, Смирнов, Кузнецов (!) |
| George | Георгий, Юрий, Егор, Джордж |

## Sample-спец случаи

- `current` (e114): даст «нынешний/текущий/современный/поток/течение» —
  правильного «до настоящего времени» нет (смотри COMPARISON_REPORT:
  contextual NO_MATCH).
- `@ Giants`, `Red Box`, `National Football League Round 6` — NO_MATCH.
- entities: Toronto Maple Leafs — NO_MATCH (нет в Wiktionary, в Wikidict был).

## Manual correctness (40 reused cases)

Виктионари дал кандидатов для 8/40:
- CORRECT: Yinchuan «Иньчуань», Olympic Games «Олимпийские игры/олимпиада»;
- PARTIAL: Parent (родитель/родительница), Report, Coral, Away;
- WRONG: Left Wing «левые» (позиция в хоккее = «левый крайний»), N/A
  («неприменимый/недоступный» — переводить N/A нельзя).

## Decision

SINGLE_CANDIDATE 11, MULTIPLE 30, NO_MATCH 159.

## Limitations

1. Небольшой охват (Buchmeier словарь ограничен темами Wiktionary-списков).
2. Сenses-чувствительность: rich candidates для common слов, но multiple
   требует context/LLM.
3. Нет frequency/probability.
