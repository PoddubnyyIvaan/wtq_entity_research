# REPORT — Эксперимент 3: OpenRussian EN→RU (обратный индекс)

## Dataset

OpenRussian.org официальные данные (`Badestrand/russian-dictionary`, CC BY-SA
4.0): nouns/verbs/adjectives/others CSV (TSV). Построен **обратный** индекс:
каждая EN-глосса из `translations_en` → RU слово (45 328 ключей).

## Sample

`sample_200.jsonl` — тот же n=200 (seed 42).

## Lookup metrics (dictionary-only)

| Метрика | Значение |
|---|---|
| matched | **32 / 200 (16%)** |
| no_match | 168 (84%) |
| single / multiple | 11 / 21 |
| matched COMMON_WORD | 16 / 48 (33%) |
| matched NAMED_ENTITY | 14 / 121 (12%) |
| matched UNKNOWN | 2 / 7 |
| matched JUNK | 0 / 24 |

## Многозначные слова (сохранили)

| Слово | Кандидаты |
|---|---|
| current | течение, поток, ток, струя, текущий, ходячий |
| match | партия, встреча, матч |
| record | список, запись, рекорд |
| field | поле, полоса, нива |
| Private | солдат, боец, личный, частный |
| link | связь, ссылка, звено, ниточка |
| Away | прочь, подальше |

## Особенности

- Словарь рус-ориентирован: EN gloss — это английские переводы RU слов;
  после обратного индекса RU-кандидаты — **lemma формы** (жилой, родитель,
  лев) с ударением в поле accented; формы/POS можно добавить для ranking.
- Только одиночные слова; фразы EN («Oil and gas») находились по частичной
  глоссе — редко.

## Manual correctness (40 reused cases)

Кандидаты у 6/40: PARTIAL: Residential «жилой», Parent «родитель», Scattering,
Coral, Report; WRONG: Leo «лев» (заглавная имена → но «Лев» тоже имя).
CORRECT: Oil and gas «нефтегазовый» (adjective, частично).

## Decision

SINGLE_CANDIDATE 11, MULTIPLE 21, NO_MATCH 168.

## Limitations

1. Обратный индекс теряет sense boundaries (глоссы объединены в один список).
2. Нет частотности глосс (нельзя отсортировать кандидаты).
3. Слова без глоccов или многоглоссовые с редкими глоссами теряются.
