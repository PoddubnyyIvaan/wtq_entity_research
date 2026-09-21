# COMPARISON_REPORT — Готовые EN→RU словари для WTQ (4 независимых эксперимента)

Все пять прогонов (4 словаря + filtered-вариант статистического) используют
один и тот же sample: n=200, seed=42, dev e001–e020 / eval e021–e200.
LLM в базовых замерах не использовался. Coverage ≠ accuracy.

## Таблица словарей

| Dictionary | Entries (index) | Coverage | Multi-candidate | No-match | Manual correctness (40 cases) |
|---|---:|---:|---:|---:|---|
| Wikidict | 564 368 | **45/200 = 22.5%** | 0 | 155 | 4 CORRECT / 6 PARTIAL / 1 WRONG (из 11) |
| Wiktionary | 1 261 (5 235 cands) | 41/200 = 20.5% | 30 | 159 | 2 CORRECT / 4 PARTIAL / 2 WRONG (из 8) |
| OpenRussian (reverse) | 45 328 | 32/200 = 16% | 21 | 168 | ~1 CORRECT / 5 PARTIAL (из 6) |
| Statistical full | 56 624 | 37/200 = 18.5% | 26 | 163 | 0 CORRECT / 5 PARTIAL (из 5) |
| Statistical filtered | 4 096 | 12/200 = 6% | 0 | 188 | 0/12 |

## Candidate union (§17)

Объединение кандидатов всех пяти словарей: **71 / 200 = 35.5%** occurrences
получают ≥1 RU-кандидата (против 22.5% у лучшего одиночного словаря).
Сопоставление ≥2 словарями: 40/200 (20%).

Типовой пример (`current`, e114):
- wikidict: «Куран» (плохая WD-title форма)
- wiktionary: нынешний, текущий, современный, поток, течение
- openrussian: течение, поток, ток, струя, текущий, ходячий
- statistical full: текущий, нынешний, ток, действовать, актуальный
- union: {текущий, нынешний, современный, поток, течение, ток, струя,
  ходячий, действовать, актуальный, куран}
→ правильно-контекстной «до настоящего времени» нет ни у кого.

## Intersection / agreement (§16, §18)

Pairwise agreement на overlapping occurrences (normalized, casefolded):

| Пары | overlapping | agree | rate |
|---|---:|---:|---:|
| wiktionary vs openrussian | 28 | 26 | **0.93** |
| wiktionary vs statistical_full | 29 | 27 | **0.93** |
| wiktionary vs statistical_filtered | 11 | 11 | **1.00** |
| openrussian vs statistical_full | 28 | 22 | 0.79 |
| openrussian vs statistical_filtered | 11 | 9 | 0.82 |
| statistical full vs filtered | 12 | 12 | 1.00 |
| wikidict vs statistical_full | 19 | 12 | 0.63 |
| wikidict vs wiktionary | 22 | 13 | 0.59 |
| wikidict vs openrussian | 16 | 6 | 0.38 |

- agreement ≠ correctness: bank/agree=«банк» может быть неверным в контексте
  «river bank»; но **высокое соглашение ≥0.9 — реалистичный confidence-сигнал**
  для common-word TOP-1 (не для entities).
- Wikidict — аутлаер: это WD-titles, а не лексикон (entity-поверхности,
  дескриптивные названия), он редко даёт общесловарные формы.

## Особые WTQ cases (§19)

FOUND в sample (11): Yinchuan, Red Box, @ Giants, NFL Round 6, current,
Ha-218, Fashion Magazine, Student/Model, Allsvenskan, Toronto Maple Leafs,
Cooper-Maserati. NOT_FOUND_IN_SAMPLE (7): Smith, Smyth, New York, London,
George, Arsenal, Washington — эти 7 проверены словарно:

| Слово | Wikidict | Wiktionary | OpenRussian | Stat full | Stat filtered |
|---|---|---|---|---|---|
| Smith | Смит | кузнец/Смирнов/Кузнецов | кузнец | смит | смит |
| Smyth | — (нет) | — | — | — | — |
| New York | Нью-Йорк (штат) | нью-йоркский; штат Нью-Йорк | — | — | — |
| London | Лондон | Лондон, лондонский | Лондон, лондонский | лондон | лондон |
| George | Георге | Георгий, Юрий, Егор, Джордж | — | джордж, георгий, жорж | джордж |
| Arsenal | (нет RU? сущ.) | — | — | — | — |
| Washington | Вашингтон | Вашингтон | — | вашингтон | вашингтон |

Ключевые наблюдения:
- **Smyth отсутствует во всех пяти** — коллизия неразрешима словарями;
- «Smith» в Wiktionary/OpenRussian = «кузнец/Смирнов/Кузнецов» (common-sense
  фамилия-профессия), что для персоналии WRONG (identity-ловушка);
- statistical даёт «смит» (transliteration) — в таблице WTQ USA может
  быть приемлемо, но «Смит» традиционнее.

## Qwen reranking (optional, §11)

77 multiple-candidate случаев: **36 numeric pick / 22 NO_MATCH / 19
format-break** (3B модель; печаль: «…|NO_MATCH» ответы, мы починили parse).
Результаты: `rerank_results.json` — отдельный артефакт, не gold.

## Ответы на §25

1. **Наибольшее coverage (как сам)**: Wikidict 22.5%.
2. **Больше альтернатив**: Wiktionary (mean candidates >3 у matched, senses
   сохранены), затем statistical_full (3.86/word).
3. **Согласованы**: wiktionary ↔ openrussian (0.93), wiktionary ↔ statistical
   (0.93); wikidict — аутлаер (WD-titles).
4. **Покрывают разные слова**: да: union 35.5% vs best single 22.5% (+13 пп).
5. **WTQ-specific vocabulary**: статистический full хорошо ловит slang/US
   («petrol»? нет — «petrol» в OpenRussian; в statistical: petrol→бензин есть);
   OpenRussian лучший на редких common словах; Wikidict — на entity titles.
6. **Intersection как confidence**: да, для COMMON_WORD: согласие wiktionary
   + openrussian + statistical — сильный (но не gold) сигнал.
7. **Union как candidate generator**: да: 35.5% покрытия, но candidate list
   требует ranking (probability/count/top-1).
8. **count/probability**: mean top-1 p=0.584; помогает выбрать дефолт
   («книга», «банк», «текущий»), но не решает context-switch («current»).
9. **Для named entities**: только Wikidict покрывает entity-titles
   (24% NAMED_ENTITY), остальные словари — нет (нужны ParaNames/Wikidata).
10. **Только common words**: Wiktionary, OpenRussian, Statistical.
11. **Требуют context**: current, book, match, round, record, field, Private,
    Away, link, Parent — multi-sense common words.
12. **Требуют LLM**: случаи, где candidate list не содержит правильной
    формы (current→«до настоящего времени», Left Wing→«левый крайний»),
    и multi-sense выбор при отсутствии statistics.
13. **Manual review**: NO_MATCH для NAMED_ENTITY (в dictionary-слое это
    норма → передавать в entity pipeline), WRONG single candidates
    (Changelog → «Журнализация…», N/A → «неприменимый»), multi-candidates
    с грубым ranking.

## Архитектурные роли (§24)

```text
COMMON_WORD  → dictionary (Wiktionary > OpenRussian > Statistical > Wikidict*)
NAMED_ENTITY → ParaNames / Wikidata / Wikipedia (identity-путь)
NUMBER/DATE  → immutable, не переводить
JUNK         → preserve verbatim
```
*Wikidict полезен для entity-поверхностей (то же, что ParaNames-ish),
но опасен для common слов.

## Итог по главному вопросу

> Можно ли существенно заменить LLM для перевода обычной лексики WTQ
> комбинацией готовых EN→RU словарей?

Частично: union словарей покрывает 35.5% WTQ-строк (в основном
COMMON_WORD: 33-44% у лексических словарей), и для ~20% sample дают
согласованные (≥2 словаря) кандидаты. Для остальной лексики нужен
сущностный/LLM слой. Перевод без LLM невозможен для multi-sense
(common words) и entities.

> Можно ли использовать agreement нескольких независимых словарей как
> deterministic confidence signal?

Да — как **сигнал**, не как correctness: пары wiktionary/openrussian и
wiktionary/statistical согласуются на 93% overlapping occurrences;
пересечение ≥2 словарей наблюдается для 40/200. Это cheap deterministic
routing signal: 2+ словаря согласились → кандидата можно ставить top-1
для COMMON_WORD; иначе — REVIEW/context/LLM.
