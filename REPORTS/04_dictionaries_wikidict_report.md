# REPORT — Эксперимент 1: Wikidict EN→RU (Wikidata-derived DSL)

## Dataset

Wikidata interwiki-derived словарь (`wikidict-dsl-ru`), 628 522 декларативных
статей (README), наш индекс: 564 368 normalized EN heads. Формат: пары
`headword / RU-строка`; без POS/senses/frequency (см. DATASET_INFO.md).

## Sample

`sample_200.jsonl` — тот же n=200 (seed 42), dev e001–e020 / eval e021–e200.

## Lookup metrics (dictionary-only)

| Метрика | Значение |
|---|---|
| matched | **45 / 200 (22.5%)** |
| unique EN forms | 190 |
| no_match | 155 (77.5%) |
| single / multiple | 45 / 0 (одна RU-строка на headword; множественность возникает только у разных headwords с одним нормализованным ключом) |
| matched COMMON_WORD | 14 / 48 (29%) |
| matched NAMED_ENTITY | 29 / 121 (24%) |
| matched JUNK | 0 / 24 |
| matched UNKNOWN | 2 / 7 |

NO_MATCH — не ошибка (см. протокол).

## Особый интерес

| Слово | Wikidict |
|---|---|
| current | «Куран» (!) — из-за Wikidata-уникального surface (канд. «Куран» = иная сущность) |
| book | «Книга» |
| bank | «Банк» |
| Smith | «Смит» |
| London | «Лондон» |
| George | «Георге» (частично; wd RU label другой титула «Георге») |
| Washington | «Вашингтон» |
| New York | «Нью-Йорк (штат)» — служебная скобка |

## Важные особенности

1. Словарь = Wiki-**titles**, поэтому капитализация «Книга»/«Банк» (title case);
   для common words поверхность чуть неестественна.
2. «current» демонстрирует главный риск: WD-title словарь даёт «Куран»
   (сущность-радиостанцию/«куран» русское слово?) вместо common-word
   значения. При lookup common-слов Wikidict опасен: surface = entity title.
3. Появляются дескриптивные названия («Чемпионат Швеции по футболу»).

## Manual correctness (40 reused manual cases)

На 40 предыдущих manual-кейсах wikidict дал кандидатов для 11:
CORRECT 4 (Buffalo Bills «Баффало Биллс», Yinchuan «Иньчуань», Olympic Games,
Toronto Maple Leafs «Торонто Мейпл Лифс»); PARTIAL 6 (инвертированные
«Андретти, Майкл», «Кейдж, Майкл», «Северн, Дэн», дескриптивные Allsvenskan,
Giant Slalom, нефтегазовый); WRONG 1 (Changelog → «Журнализация изменений
проекта»).

## Cases

- `FOUND` в sample (11/18): Yinchuan, Red Box, @ Giants, National Football
  League Round 6, current, Ha-218, Fashion Magazine, Student/Model,
  Allsvenskan, Toronto Maple Leafs, Cooper-Maserati.
- Синтетические (Smith/Smyth/New York/London/George/Arsenal/Washington) —
  NOT_FOUND_IN_SAMPLE; проверены словарно (см. таблицу в COMPARISON_REPORT).

## Decision

- dictionary-only: SINGLE_CANDIDATE 45, NO_MATCH 155.
- Полные записи: `results.jsonl` (schema §21).

## Limitations

- Одиночная RU-строка не содержит senses/POS.
- Title-case формы для common слов.
- Нет frequency/score.
