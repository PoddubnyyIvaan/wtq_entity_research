# ParaNames experiment

Вопрос: может ли ParaNames надёжно давать русскую surface form для named
entities WTQ, сохраняя identity, и можно ли ставить его первым словарным
слоем перед Wikidata / Wikipedia / LLM.

## Dataset

- ParaNames 1.0, релиз **v2024.05.07.0**, официальный GitHub `bltlab/paranames`
  (лицензия MIT; Wikidata dump 2024-03-13). Подробности: `DATASET_INFO.md`.
- Файл `paranames.tsv.gz` (999 401 108 B; 140 140 300 строк) —
  `wikidata_id | eng | label | language | type ∈ {PER, LOC, ORG}`.
- EN-строк 17 154 540; **RU-строк 1 534 139**; ключей EN→RU **1 260 283**.
- Доля строк по типам: PER 93.7M, LOC 29.7M, ORG 16.7M.

## Sample

Тот же sample (`wtq_entity_research/samples/sample200.jsonl`, n=200,
seed=42; dev e001–e020 / eval e021–e200). Копия для отчёта:
`experiments/paranames/sample_200.jsonl`.

## Coverage

| Замер | Значение |
|---|---|
| Примеры с ParaNames-матчем | **49 / 200 = 24.5%** |
| из них single / multiple | 31 / 18 |
| пути: en_key / qid / none | 38 / 11 / 151 |
| NO_MATCH, но Wikidata имеет RU-форму | 65 / 151 |
| Wikidata RU-form coverage (тот же sample) | **110 / 200 = 55%** |
| Qwen (mode D) дал RU-форму | 106 / 200 (эксперимент 1) |

Coverage ≠ accuracy (не подтверждена identity на всём sample).

## Coverage by entity type

| Тип | PN match | Wikidata RU | n |
|---|---|---|---|
| PERSON | 12 (40%) | 18 (60%) | 30 |
| SURNAME | 4 (27%) | 12 (80%) | 15 |
| LOCATION | 12 (48%) | 15 (60%) | 25 |
| ORGANIZATION | 6 (30%) | 11 (55%) | 20 |
| SPORTS_TEAM | 3 (15%) | 8 (40%) | 20 |
| EVENT_WORK | 4 (16%) | 14 (56%) | 25 |
| MULTI_WORD | 1 (5%) | 9 (45%) | 20 |
| SHORT_AMBIGUOUS | 4 (20%) | 8 (40%) | 20 |
| FALSE_POSITIVE | 2 (13%) | 13 (87%) | 15 |
| UNKNOWN | 1 (10%) | 4 (40%) | 10 |

ParaNames не опережает Wikidata ни в одном типе. Сильная сторона —
canonical LOC/PER названия. Пропадает на alias-формах WTQ
(`Student/Model`, `All American Racing`, `Cooper-Maserati`, `@ Giants`).

## Candidate multiplicity

- single 31, multiple 18, none 151.
- У multiple встречаются дубли (тот же RU с разными QID → `Yinchuan`,
  `Avalon`) и разные RU разных QID (`Walton`, `Manchester`, `Marathon`,
  `Sharp, Marshall → Маршалловы Острова` (identity ошибка из-за
  reverse-order фамилии)).

## RU collisions (весь индекс)

Доля RU-надписей, встречающихся у >1 QID:

| Тип | distinct RU | colliding | rate |
|---|---|---|---|
| LOC | 300 406 | 42 790 | **14.2%** |
| ORG | 169 073 | 9 241 | 5.5% |
| PER | 860 021 | 42 719 | 5.0% |

Локационные имена в RU коллидируют чаще всего (одноимённые города/деревни
в разных странах и т.д.).

## ParaNames vs Wikidata

| Пересечение | n |
|---|---|
| оба источника дали RU | 47 |
| только ParaNames | 2 (Avalon → Авалон, Havoc → Хэвок) |
| только Wikidata | 65 |

- На 47 «обоих» поверхностные формы различаются у 26 (normalized) —
  фактически из-за перестановок `Баффало/Буффало`, инвертированного
  порядка «Фамилия, Имя» в WD (WD даёт «Северн, Дэн»; PN даёт
  «Дэн Северн» — для surface form это почти всегда **лучше**).
- identity-path проверка: у 27 QID есть RU в ParaNames; **совпадение
  нормализованной формы = 14/27 ≈ 52%**; остальное — вариантные записи
  (`Буффало Биллс` vs `Баффало Биллс`) или разные label (WD может
  использовать alias).

## ParaNames vs Wikipedia

Значения Wikipedia (ru) из langlinks предыдущего эксперимента
(exp3_sources.jsonl) полностью совпадают с Wikidata sitelink (эксперимент 3),
так что в таблице ниже Wikipedia == Wikidata — они не независимые источники.

## ParaNames vs transliteration

ParaNames даёт традиционные формы, которых у простых транслитерационных
правил нет (см. «New York→Нью-Йорк», «London→Лондон», «George→Джордж» из
probe, всё из ParaNames). Но фамилии:
- **`Smith → NO CANDIDATE`**
- **`Smyth → NO CANDIDATE`**
(обязательный кейс: в ParaNames нет RU-надписи для этих WD PER-сущностей)
→ ParaNames НЕ покрывает самый простой surname-fallback; транслитерация
всё ещё нужна как нижний fallback. Для 5/7 тестируемых имён ParaNames даёт
традиционную форму.

## Context reranking (Variant B)

18 multiple-candidate кейсов переданы Qwen2.5:3b строго для выбора
(«candidate_id only, no generation»):

- корректное числовое pick: 10/18 (например `Yinchuan → Иньчуань`,
  `Robert Smith → Роберт Смит`, `Handan → Ханьдань`);
- честный NO_MATCH: 5/18 (нет информации для выбора: `Marathon`,
  `Honda`, `Walton`);
- отсутствие числового выбора: 4/18 (`Leo`, `Kirkkonummi`, `Manchester`,
  `Rita`, `Clay`) — нарушает формат (выводит имя, не ID) —
  означает, что автоматический выбор с 3B ненадёжен.

## Harmful substitutions

Типовые identity-ошибки (примеры из sample):

| source | куда | оценка |
|---|---|---|
| `Sharp, Marshall` (PERSON) | «Маршалловы Острова» (LOC) | **IDENTITY_ERROR** |
| `6th` (FALSE_POSITIVE) | «Массачусетс» | **IDENTITY_ERROR** |
| `N/A` (FP) | сущность с RU | потенциальная опасность (AUTO-ACCEPT не делается) |

Классификация ошибок (§16): IDENTITY_ERROR — когда PN предлагает RU для
**другого** QID. Base: 47 «обоих», но только 14 normalized-equal;
15 расхождений — вариант формы, 13 — вероятно другой entity/label. На 40
manual reuse-кейсах опасных PN-подстановок не было (PN не предлагает форму
там, где не знает ключ); из этих 40 — 13 ACCEPT, 27 NO_MATCH.

## Required manual review

По правилу (§12): ACCEPT 37 / REVIEW 12 / NO_MATCH 151.
Доля «entity-типов», где требуется ручная оценка после контекстного
reranking — только 12 multiple + часть похожих single с сомнительной
формой (выборка конфликтов `Буффало/Баффало`, `Купер` vs «Купер (команда
Формулы-1)»).

## Case studies

### Вариант A (ParaNames only) — словарные пробы (не WTQ sample!)

| Entity | ParaNames |
|---|---|
| Smith | NO CANDIDATE |
| Smyth | NO CANDIDATE |
| New York | Нью-Йорк (LOC/ORG, 2) |
| London | Лондон (12 cand.) |
| George | Джордж / Георгий / Дьёрдь (11 cand.,PER/LOC/ORG) |
| Arsenal | Арсенал (2) |
| Washington | Вашингтон (20) |

`FOUND`/`NOT_FOUND_IN_SAMPLE` (см. таблицу ниже) — sample не содержит
синтетические кейсы; они проверены словарно, **не** как sample-строки.

### Примеры из 40 reused manual cases (полная таблица — `results_40cases.json`)

| Entity | Type | ParaNames | Wikidata | Wikipedia | Qwen | Identity | Decision |
|---|---|---|---|---|---|---|---|
| Yinchuan | LOCATION | Иньчуань | Иньчуань | Иньчуань | Йинчжоу | same QID | CORRECT (PN+WD) |
| Toronto Maple Leafs | SPORTS_TEAM | Торонто Мейпл Лифс | Торонто Мейпл Лифс | Торонто Мейпл Лифс | Торонто Мэйпл Лифс | same QID | CORRECT |
| Buffalo Bills | SPORTS_TEAM | Буффало Биллс | Баффало Биллс | Баффало Биллс | Бронкос | same QID (вариант «Буффало/Баффало») | CORRECT |
| Allsvenskan | EVENT_WORK | Чемпионат Швеции по футболу | Чемпионат Швеции по футболу | Чемпионат Швеции по футболу | Алсвенскан | same QID | CORRECT (дескриптивная форма) |
| Michael Andretti | PERSON | Майкл Андретти | Андретти, Майкл | Андретти, Майкл | Майкл Андетти | same QID | CORRECT (PN естественней) |
| Dan Severn | PERSON | Дэн Северн | Северн, Дэн | Северн, Дэн | Дэн Северн | same QID | CORRECT |
| Michael Cage | PERSON | Майкл Кейдж | Кейдж, Майкл | Кейдж, Майкл | Майкл Кэсси | same QID | CORRECT (PN естественней) |
| Islahuddin Siddique | PERSON | Ислахуддин Сиддикуи | Сиддикуи, Ислахуддин | Сиддикуи, Ислахуддин | Ислахуддин Сиддик | same QID | CORRECT (PN естественней) |
| Cooper-Maserati | ORGANIZATION | Купер | Купер (команда Формулы-1) | Купер (команда Формулы-1) | Коупер-Мазерата | same QID | CORRECT (PN чище) |
| LSE: BP | ORGANIZATION | «Би-Пи» | BP | BP | ЛСЕ: БП | same QID | CORRECT (PN ≈ brand form) |
| Civil parish | OTHER-ish | община Англии | община Шотландии | — | губерния | **разные QID** (WD дал Scotland) | WRONG_RUSSIAN_FORM (WD) |
| Oil and gas / Red Box / Changelog / Ha-218 / N/A … | — | NO | junk (WD тоже дал мусор) | — | junk | — | NO_MATCH → fallback |
| Student/Model, Fashion Magazine, All American Racing, Husqvarna, Real-time | — | NO | частично (Fashion Magazine → журнал мод) | — | переменно (Fashion Magazine: WD лучше) | — | NEED WD/context |

## Limitations

1. ParaNames — только Wikidata canonical labels (не aliases, не sitelinks);
   alias-поверхностные формы WTQ не находились напрямую (65/151 NO_MATCH при
   наличии WD RU-формы; 11 из них покрыты через QID-путь).
2. Identity: сравнение строк ≠ identity; identity проверена только через
   QID-совпадение (27/200 примеров).
3. В релизе нет score/frequency/priority; кандидаты выдаются в порядке строк файла.
4. Из 200 примеров реальных «имя-собственных» ~185: часть — табличный
   мусор; доля 24.5% относится именно к этому sample.

## Сравнение с baseline предыдущих этапов

Замеры по одному и тому же sample (n=200, seed=42):

| Метод | EN-name matched | RU form | Identity verified | Согласование формы с WD |
|---|---:|---:|---:|---:|
| Wikidata resolver (exp2) | 97.5% QID | **55%** | 34.8% (обратным поиском) | — |
| ParaNames (EN-key + QID) | 24.5% | 24.5% | 27 QID | 14/27 ≈ 52% (normalized) |
| ParaNames + context rerank | 24.5% | 24.5% | как PN | pick 10/18 multiple |
| Транслитерация (+словарь) | 100% (генерация) | 100% (без словаря — низкое согласование) | нет | 4.5% правил |
| Qwen 2.5 3B (mode D) | 106/200 RU-форм | 106/200 | нет | подмены ≈28% (ручная оценка) |

Это accuracy только в смысле ручных повторных оценок; это coverage/agreement-метрики, а не accuracy без человеческого gold на всём sample.

## Ответы на вопросы эксперимента (§24)

1. **Покрытие WTQ**: 24.5% (49/200) — сопоставимо с 55% у Wikidata.
2. **Полезные типы**: LOCATION (48%), PERSON (40%) — canonical names; SURNAME/SPORTS_TEAM (27%) — хуже всего на фамилиях и командах.
3. **Несколько вариантов**: 18/49 матчей (multiple) — 9% всего sample.
4. **RU collisions**: LOC 14.2%, ORG 5.5%, PER 5.0% (весь индекс).
5. **RU-формы вне Wikidata**: да — 2 примера (Avalon→Авалон, Havoc→Хэвок); mostly вариантные написания (Буффало/Баффало).
6. **ParaNames лучше Wikidata**: поверхностные формы для persons («Дэн Северн» против «Северн, Дэн») и организаций («Купер» без служебной скобки).
7. **Identity errors**: да — `Sharp, Marshall → Маршалловы Острова`, `6th → Массачусетс`, и 13/47 «обоих»-пец с несовпадающим нормализованные формы, у которых вероятная разная сущность.
8. **Context reranking**: помогает, но хрупко: 10/18 корректный числовой выбор, 4/18 format-ошибки Qwen.
9. **Первый lookup layer**: да, в hybrid (см. Recommendation) — это даёт ~25% покрытия бесплатно.
10. **Что всё ещё требует WD/Wikipedia/manual**: alias-формы, multiword team names, `Smith/Smyth`-класс фамилий, table junk, multiple-кандидаты с одинаковым RU.

## Recommendation

- ParaNames **не может заменить** Wikidata как resolver: покрытие 24.5%
  против 55% ниже по всем типам.
- **Но когда match есть**, в ≈52% identity-path случаях он даёт эквивалентную
  форму, а для людей/локаций часто более **естественную surface form**, чем
  WD label (инвертированный порядок, служебные скобки).
- Как **первый lookup layer** — возможна hybrid-стратегия:

```text
English entity
  ↓ ParaNames EN-key exact (identity через общий QID)
  ↓ если single → кандидат; если multiple → WD/QID-разрул
  ↓ если none → WD resolver (как сейчас) → TM → транслит → LLM
```

- ParaNames NOT покрывает: фамилии без RU label у WD (`Smith/Smyth`),
  alias-form, table-specific junk — для них всё ещё нужны
  транслитерация/WD/articles/manual review.
- Context reranking (Qwen) работает, но хрупок (4/18 не формата число);
  применяется только к multiple кейсам (9% sample).
