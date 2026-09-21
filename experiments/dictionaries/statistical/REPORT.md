# REPORT — Эксперимент 4: Statistical EN→RU (KvaytG, 4A full / 4B filtered)

## Dataset

KvaytG parquet dictionaries (получены с HuggingFace):
- 4A full: 56 624 пары (count, probability);
- 4B filtered: 4 096 пар (count≥1000, probability≥0.5).
Поля: english_word, russian_word, count, probability.

## Sample

`sample_200.jsonl` — тот же n=200 (seed 42).

## Lookup metrics (dictionary-only)

| Метрика | 4A full | 4B filtered |
|---|---|---|
| matched | **37 / 200 (18.5%)** | **12 / 200 (6%)** |
| no_match | 163 | 188 |
| single / multiple | 11 / 26 | 12 / 0 |
| mean candidate count | 3.86 | 1.0 |
| mean top-1 probability | 0.584 | ~0.87 (порог) |
| matched COMMON_WORD | 14 / 48 (29%) | 3 / 48 (6%) |
| matched NAMED_ENTITY | 22 / 121 (18%) | 9 / 121 (7%) |

## probability/count как ranking

- `book`: книга (p=?), бронирование, забронировать — верно сохранены
  разные senses; top-1 by probability = «книга» (правильный дефолт).
- `bank`: банк, банковский, берег; top-1 = «банк» — в большинстве контекстов
  WTQ (колонки типа «Bank») это уже хорошо.
- `current`: текущий(0.60), нынешний, ток, действовать, актуальный,
  современный — top-1 «текущий» близок, но правильный «до настоящего
  времени» отсутствует; вероятность НЕ решает context (e114).
- `George`: джордж, георгий, жорж — top-1 «джордж» — это transliteration
  (иногда правильно для WTQ-US контекста).

Вывод: probability полезна как ranking-signal для top-1 в COMMON_WORD,
но не как истинная вероятность конкретного WTQ-контекста.

## Manual correctness (40 reused cases)

Кандидаты у 5/40 (только full): PARTIAL: Residential «жилой» (жилое), Report,
Leo «лео/лев», Parent «родитель», Coral «коралл/коралловый»; остальное NO_MATCH.

## Decision

4A: SINGLE 11 / MULTIPLE 26 / NO_MATCH 163; 4B: SINGLE 12 / NO_MATCH 188.

## Limitations

1. Небольшой словарь (56k) — много common слов из WTQ отсутствует
   (`Residential` есть, `Finally` есть только в full; filtered совсем мал).
2. count/probability — alignment-статистика, а не словарная вероятность.
3. Filtered словарь (4k) слишком мал для WTQ; полезен только для top-слов.
