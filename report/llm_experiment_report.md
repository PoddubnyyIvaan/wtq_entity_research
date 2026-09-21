# LLM experiments report (Experiment 1 + Experiment 6E)

Model: **qwen2.5:3b** (Ollama v0.12.5, CPU 12 cores, 15 GiB RAM / no GPU),
endpoint `http://localhost:11434/v1`, temperature 0.0, max_tokens 350,
prompt `exp1_v2.txt` / `judge_v1.txt`, sample seed 42, sample n=200
(dev e001–e020, eval e021–e200). Note: Ollama chat has no guaranteed
determinism; temperature=0 reduces but does not eliminate variance.

Baseline from previous stage:
- Wikidata candidate coverage 97.5%, RU-form coverage 56%
- Round-trip exact 5.4%; entity identity verified 34.8%
- Rule-based manual-review rate ≈51%; rule/manual 30/40 strict, 4 partial, 6 wrong

---

## 1. Technical pipeline

- smoke tests passed after 1 prompt revision: qwen2.5:3b responded with
  Chinese / repeated the question when the task line came before context
  (prompt_v1) → **prompt_v2** moved the task definition before the cell and
  banned answering the question → problem eliminated (saved as
  `prompts/exp1_v1.txt`→`exp1_v2.txt`).
- Pilot 5: 20/20 parsed, no hallucinated entities (one meaning shift found,
  see modes), 0.74 s mean latency.
- Pilot 20: 80/80 parse; is_entity stable across modes 17/20;
  translations differ across modes for 13/20 → context changes output.

## 2. Experiment 1 — 200 × 4 modes (800 requests)

`results/exp1_llm_context.jsonl` (+ `..._stats.json`):

| метрика | значение |
|---|---|
| parse success | **97.75%** (782/800, 18 failures, no HTTP errors) |
| mean / median / p95 latency | **0.83 / 0.81 / 1.02 s** |
| total runtime | 660 s (CPU) |
| entities detected (share per mode) | A 0.53, B 0.52, C 0.56, D 0.55 |
| is_entity stable across modes | 158 / 200 |
| entity_type stable across modes | 137 / 200 |
| **translation differs across modes** | **112 / 200** |
| self-reported `needs_review` | **0 / 800** |

Type distribution (mode D): NONE 86, ORGANIZATION 46, PERSON 27, OTHER 24,
LOCATION 11, EVENT_WORK 2 (+4 parse fails). Entity detection under-calls:
~55% vs ~92% per strata profile (SHORT_AMBIGUOUS, MULTI_WORD and
UNKNOWN strata are easily classified as „not entities").

### Answers to context questions

- **Q1 column header: помогает.** B vs A: fewer NON-entity labels
  ("Fashion Magazine" gets ORGANIZATION with header, NONE without in some
  runs), type stability higher (16/20 → 137/200 consistent overall).
- **Q2 row context: помогает, но меньше** чем header: 
  entity share +3.8 pp vs A; C хуже по стабильности (cases like "Not Free"
  меняются).
- **Q3 WTQ question: помогает в resolution, вреден в изоляции.** Mode D
  корректнее для GAA-vs-NFL кейсов (e007 перевод устойчив),но при этом
  он вводил модель в ответ-на-вопрос (fixed by prompt_v2).
- **Q4 page title: полезен слабо**; в Mode D нет отдельной ablation против
  C, но e140 table-title influences how operetta is translated.
- **Q5 минимальный context: cell + column header** — остальное повышает
  точность interpretation, но также повышает variability (responses в
  режимах C/D аналогичны, D добавляет ещё ~2% entity share).

## 3. Entity identity basics

- Сравнение с resolver (exp2): в 195 QID-linked примерах LLM translation
  and WD RU form НЕ совпадают в 61% просто из-за разных transliteration
  choices; identity можно проверить только через interpretation + entity_ok
  (judge - секция 4).
- Smith/Smyth → Смит оба (обязательный кейс): confirmed; одинаковая RU
 SURFACE form не должна считаться потерей identity (both PERSON).
- **George → "Гейри"** (обязательный кейс): **ошибочная традиционная форма**
  (правильно: Джордж) — 3B не знает traditional first-name forms даже при
  контексте; подтверждаетTranslation memory нужно.

## 4. Experiment 6E — LLM judge

`results/exp6e_llm_judge.jsonl` (+stats): 200 items, mode-D translations,
**parse success 100%**, mean latency 0.93 s, p95 1.3 s.

Global judge rates: `needs_review` **93%**, `harmful_substitution` 2%.
Judge parses well but **needs_review почти всегда true** → как standalone
review-фильтр не работает.

Judge vs моя повторная разметка 40 примеров — **относительно уже
LLM-переводов** (`results/gold_llm_translations_40.json`):

| Сравнение | Результат |
|---|---|
| harmful flag согласие | 29/40 |
| needs_review согласие | **22/40** |
| semantic_ok согласие | 31/40 |
| комбинированное правило (rule status ∧ judge) | 22/40 |
| мои ставки: review rate 55%, harm rate 28% (на LLM-переводах) | — |

**Harmful substitutions у LLM-переводов:** ~28% в manual subset
(à Buffalo Bills → «Бронкос», Yinchuan → «Йинчжоу», @ Giants → «@ Гэйнзс»,
Changelog → «Изменения в чехле», All American Racing → «Американская нация
Радиокар», BMW Motorsport GmbH → «БМВ Мотостарштагг», Civil parish →
«губерния», OR 99W northeast → «юго-западнее» (direction flip)). The judge
catches only 2/6 таких уверенных garbled substitutions → judge НЕ является
надёжным блокировщиком.

**Judge false positives (needs_review=True при корректном переводе):**
7/33 корректных примеров flagged (e.g. Toronto Maple Leafs → Торонто Мэйпл
Лифс, Olympic Games → Олимпийские игры). Judge review rate 93% против
rule-based 51% — при том что точность ниже.

## 5. Сравнение с baseline (правило vs judge)

| Метрика | rule-based stage 1 | LLM judge stage 1 (qwen 3B) |
|---|---|---|
| Согласие с ручной разметкой 40 | **30/40 strict** (WD-suggestion) | 22/40 (LLM-translation) |
| Substitution recall | — (rule REJECT branch отсутствует) | 2/6 ≈ 33% |
| needs-review rate | 51% | 93% |
| Отдельные harmful предложения | ~20% (auto-accepted) | 28% поверхности |

Несовпадение выборок (WD form vs LLM form) — сравнение количественно не равнозначно; главное: **LLM add-on не улучшил согласование** с человеком при
3B-модели, а качество самой генерации хуже (неизвестно; надо выверять финальные формы отдельно).

## 6. Rate of unresolved errors

Остались нерешёнными:
- многословные club/team names (`World Indoor Championships → «Мировые
  индустриальные чемпионаты»` — wrong «indoor» reading);
- традиционные русские формы имён (George → «Гейри» вместо «Джордж»);
направления в названиях дорог (`northeast→юго-западнее`);
- brand-like cells (Fashion Magazine, All American Racing, Student/Model)
  как бренды vs generic words;
- GAA league vs American NFL context switch.

## 7. Q-ответы

- **Q1 (header)**: да, помогает наиболее предсказуемо (type stability 137/200
  против 0 базово; entity share меняется при mode B+).
- **Q2 (row): помогает, но частично** (C/D дают корректнее interpretation),
  но добавляет variability переводов (112/200 differ across modes).
- **Q3 (question): помогает только когда подан справа/после задачи**; в v1
  даже вредил; после prompt_v2 валиден для disambiguation.
- **Q4 (page title): влияет меньше;** улучшает interpretation для
  discontinued items, но вредит для generic-слов (Тrow="">
- **Q5 (минимальный context)**: cell + column header… этого достаточно для
  base quality; row добавляет понятие *what kind of row*, question +
  title не добавляют стабильности (по этому sample).
- **Q6 (перевод после resolver)**: частично; при ID с подтвержденной
  identity → model справляется (Buffalo Bills + WD form ID), но
  самостоятельно делает substitutions.
- **Q7 (entity type сам)**: согласие strata ~53-56% (то есть понимает
  PERSON/LOCATION/ORGANIZATION но ставит NONE очень часто для SHORT_
  AMBIGUOUS и MULTI_WORD); не надёжно для коротких амбивалентных (short
  ambiguous, RED Box).
- **Q8 (harmful substitutions): 28% на LLM-переводах** (vs ~20% на top-1
  WD предложений) — оба источника intake risk, LLM не снижает.
- **Q9 judge снижение fragmentation**: не снижает; правило и judge дают
  различные reviews, по 40 примерам 22/40 согласованность (roughly random).
- **Q10 review rate**: не снижает — если фильтровать только LLM-judge,
  то 93% вверх вместо 51% rule.
- **Q11 нерешённые ошибки**: см. секцию 6.
- **Q12 где применять LLM**: с qwen2.5:3b — **только как поверхresolver'а,
  после resolver'а** (сaintly проверка interpretation поверх QID), но
  как judge сейчас не достаточно стабилен для того чтобы полностью заменить
  rule-based QC (needs_review 93% — шум).

## 8. С concluding note

Qwen 2.5 3B на данном sample: *stable JSON* (98%), *cheap* (0.83 s/req), но
качество entity translation ниже, чем сиделка Wikidata RU form (где она
есть), и самостоятельное определение типа ненадёжно для коротких амбивалентных значений. Should improve by:
(i) resolver как FIRST класс кандидат, (ii) LLM as formatting localizer
(если resolver дал ru form с сервера; LLM полирует surface), (iii) LLM-judge
только as enrichment к rule-based, никогда как standalone.
