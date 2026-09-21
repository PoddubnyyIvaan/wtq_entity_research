# wtq_entity_research — исследование перевода сущностей и лексики WTQ (EN → RU)

Полная постановка задачи: `REPORTS/00_ПОСТАНОВКА_ЭКСПЕРИМЕНТОВ.md`.
Главная цель: определить, как переводить ячейки WikiTableQuestions на русский,
сохраняя identity сущности и естественную русскую surface form, и какие
комбинации словарей/ParaNames/Wikidata/LLM/NMT/QC-правил это делают надёжнее.

## Данные и общие условия (все эксперименты)

- Датасет: `WikiTableQuestions/` (22 009 вопросов, 2 108 таблиц, 376 917 ячеек), read-only.
- Production translator: `wtq-translator/`, read-only, никогда не запускался.
- Один fixed sample на все этапы: **n=200, seed=42**, 10 стратов
  (PERSON 30, SURNAME 15, LOCATION 25, ORGANIZATION 20, SPORTS_TEAM 20,
  EVENT_WORK 25, MULTI_WORD 20, SHORT_AMBIGUOUS 20, FALSE_POSITIVE 15, UNKNOWN 10),
  dev e001–e020 / eval e021–e200 → `samples/sample200.jsonl`.
- Обязательные синтетические кейсы (отдельно, не в sample): Smith, Smyth,
  New York, London, George, Arsenal, Washington.
- Существующая CoreNLP NER-разметка (`training.tagged`, `tagged/*-tagged/*`)
  — основной источник типизации; свой NER не запускался.
- Метрики: coverage/agreement/identity — НЕ accuracy (accuracy только на
  human-40 и оговорённых подмножествах single-rater); round-trip exact — диагностика.
- Репозитории не изменялись в течение всего исследования
  (WTQ `7d455a5…`, wtq-translator `7691197…`, только pre-existing untracked `.idea/`).

## Этап 1 — Baseless baselines без LLM (Wikidata/Wikipedia/транслитерация/JRC-Names/QC)

**Как проводилось.** Потоковое профилирование WTQ → построение стратифицированного
sample из существующей CoreNLP-разметки (seed=42; всякий кандидат — ячейка 3–60
символов с буквами, без чисел/дат/процентов). Затем пять независимых экспериментов
на одном sample:

| № | Что делалось | Как | Результат (ключевой) |
|---|---|---|---|
| 0 | Copy baseline | детерминированно source→source | 100% identity, 0% RU-формы — копию можно оставить только immutable |
| 2 | Wikidata resolver | `wbsearchentities` → Wikipedia search fallback → ранжирование по string-sim + P31/header → RU форма из `sitelink > label > alias`; rate-limit 0.55 s, \retries на 429 | QID coverage **97.5%**, RU-form **55%**; naive top-1 → harmful ≈20% |
| 3 | RU-источники | langlinks (Wikipedia API) vs WD sitelink/label/aliases | langlinks ≡ sitelink (100%); label шире (+28 пп, но латиница↑); aliases почти ничего не добавляют |
| 4 | Транслитерация | BGN-подобные правила + традиционный словарь | голые правила — 4.5% согласования с WD; Smith/Smyth→Смит (коллизия) |
| 5 | JRC-Names | официальный `entities.gzip` (14.2 MB, поточный разбор) + функциональные пробы | 1.45 млн вариантов, кириллица 5.6%, **нет локаций** — как fallback персоналий |
| 6 | QC-метрики | round-trip, normalized, entity identity (reverse-lookup 60 форм), TM-консистентность; decision-правила → статусы; manual 40 кейсов | rule Q教案C: VERIFIED 33/ACCEPT 14/…, review-rate 51%; согласие rule/manual 30/40 strict |
| 6E | LLM judge — перенесён в этап 2 (нет LLM на этапе 1; BLOCKED зафиксирован) |

Как: скрипты `scripts/exp0…exp6b.py` (все raw-ответы и кэши в `results/` и `cache/`);
отчёт: `report.md` + `REPORTS/01_stage1_baselines_report.md`.

## Этап 2 — LLM-эксперименты (Ollama qwen2.5:3b, затем qwen2.5:7b на GPU)

**Как проводился**: user-space Ollama (`~/.local/opt/bin/ollama serve`); smoke-тесты
(3 прогона) выявили дефект prompt_v1 (модель отвечала на вопрос и выводила
китайский) → переписан в `prompt_v2` (обе версии в `prompts/`); pilote 5 → pilot 20 →
полный 200×4 режима A-D (cell / +column / +row / +row+column+question+title);
temperature 0.0, max_tokens 350; вычисления локальные (CPU 0.83 s/запрос).
Judge (6E) — отдельным промптом на тех же 200 и на 40 human-кейсах.

Результаты: parse 97.75%; is_entity стабильно только 158/200; перевод меняется
между режимами у 112/200; needs_review модель ставит 0/800 (самодиагностика
отсутствует); manual-40 accuracy 62.5%; harmful 27.5%; hit-rate по silver ~19%
в всех режимах; judge needs_review 93% (шум), согласие с manual 22/40.
Отчёт: `REPORTS/02_llm_experiments_report.md` (+ accuracy section);
команды: `llm_smoke_test.py`, `exp1_context.py 5|20|200`, `exp6_llm_judge.py`,
`mandatory_llm_run.py`.

## Этап 3 — ParaNames (первый lookup-слой?)

Как: официальный релиз ParaNames v2024.05.07.0 (GitHub bltlab/paranames, MIT;
Wikidata dump 2024-03-13), файл `paranames.tsv.gz` (1 GB, 140.1 млн строк),
поточный индекс: 1.53 млн RU-форм на 1.26 млн EN-ключей (+ QID→RU для 184 QID).
Variant A — dictionary only на всём sample; Variant B — Qwen rerank существующих
кандидатов (строгий формат candidate_id/NO_MATCH, генерация запрещена).
Результаты: coverage **24.5%** (49/200; ни одного типа не опережает WD 55%);
RU collisions по индексу LOC 14.2%/ORG 5.5%/PER 5%; Smith/Smyth → **NO CANDIDATE**;
New York/London/George/Arsenal/Washington — традиционные формы есть; identity-path
совпадение с WD-формой 14/27 ≈ 52%; Qwen rerank 10/18 numeric-выбор.
Отчёт: `experiments/paranames/`, `REPORTS/03_paranames_report.md`.

## Этап 4 — Готовые EN→RU словари (4 независимых)

**Как**: 5 прогонов на одном sample: Wikidict (WD interwiki DSL, 564k ключей),
Wiktionary (Buchmeier DSL .dz, 5 235 кандидатов с POS+sense), OpenRussian
(Reverse-индекс EN-gloss → RU по官方 CSVs, 45k), Statistical 20M-corpus
(HF parquet full 56 624 / filtered 4 096 с count/probability). У каждого — свой
индекс/кэш/результаты/REPORT.md (schema §21), LLM в baseline отсутствовал.
Результаты: coverage Wikidict 22.5% / Wiktionary 20.5% / OpenRussian 16% /
Statistical 18.5% / filtered 6%; **union 35.5% (+13 пп); agreement Wiktionary↔
OpenRussian/Statistical ≥0.93** — детерминированный confidence-сигнал для
common words; Smith → кузнец/Смирнов (identity-ловушка common словарей).
Отчёты: `experiments/dictionaries/`, `REPORTS/04_dictionaries_*`.

## Этап 5 — Специализированные модели (RTX 4060 8GB)

ШАГ 0 зафиксирован: GPU RTX 4060, свободно 5984 MiB (2 GB — Windows-дисплей),
torch 2.14.0+cu126, кэши в `.cache/hf` (native ext4), Ollama v0.12.5.

| Эксперимент | Как проводился | Результат |
|---|---|---|
| 5A ByT5-small FT | ParaNames PER 200k/3k/3k entity-split, bf16, grad-checkpoint, batch 32, 3 эпохи — **93 мин train, peak 2.75 GB VRAM** | ParaNames-test exact 45.6%; agreement c WD на WTQ 14.1% (BGN 7.7%); **7/7 mandatory кейсов**; 7 ms/имя инференс |
| 5B qwen2.5:7b localizer (RAG) | resolver-кандидаты в промпте; confirm/NO_CANDIDATE; parse-fail из-за `{{}}-braces был исправлен; 14b-проба (68% VRAM offload) прервана при ×5 latency | accuracymanual-40 **67.5%** (3b 62.5%), harmful **12.5%** (3b 27.5%); latency 1.32 s (медленнее 3b-CPU!); верность кандидату 19-25% |
| 5C NLLB-200-600M (CC-BY-NC) | 23 COMMON_WORD без словарного покрытия, CUDA fp16, beams=4 | 0.13 s/запрос; manual accuracy strict **47.8%** (lenient 78.3%); entity rows не подавались |
| 5D QC-классификатор | GBM на фичах предыдущих артефактов, LOO по 40 gold | agreement 65% (rule 55%, judge 55%, n=40 — PoC) |

Сравнение: `REPORTS/05_stage5_comparison.md` (+ per-experiment отчёты 05a–05d).

## Этап 6 — Candidate-Constrained Entity Selection (главный архитектурный итог)

**Как**: candidate set из существующих артефактов (WD sitelink/label/aliases +
ParaNames, provenance) → silver labels (37 surface-gold / 50 identity-gold;
ambiguous/unknown исключены) → 4 rerankers на **одинаковых** наборах:
B0 first-candidate, B1 score, B2 GBM (обучение на silver, 40 gold исключены),
Qwen3B/7B selection-only (prompt stage6_v2, temperature 0, max_tokens 120:
**генерация запрещена**, ответ только candidate_id/NO_MATCH, финал —
детерминированный COPY). Команды: `build_sets.py → baselines_and_oracle.py
(oracle|baselines|feature_reranker) → run_llm_selection.py (main/ablation/
oracle/shuffled) → evaluate.py`. LLM-прогонов ~1.400 (~30 мин).

Результаты: candidate coverage 58%; identity recall 88%; **0 harmful** на
human-40 у обоих LLM (против 11-12/40 у free-gen) — surface hallucination
устранена полностью детерминированным COPY; но NO_MATCH 71-85% (safe, но
малочитаемый контракт); контекст не улучшает selection (больше отказа);
shuffled-control: выбор не меняется при перемешанном контексте (surface
priors), 6/6 pairs same; oracle ≡ original — ranking НЕ bottleneck.

**Bottleneck**: retrieval (42% ячеек вообще без кандидатов) +
over-abstention. Продолжать LLM reranker не стоит; следующий шаг —
расширенный retrieval и fallback-цепочка (ByT5 → TM → REVIEW).
Отчёт: `experiments/stage6_candidate_selection/analysis.md`,
`REPORTS/06_stage6_analysis.md`.

## Структура каталогов

```text
wtq_entity_research/
├── README.md                        (этот файл: как всё проводилось)
├── REPORTS/                         все .md отчёты в одном месте (+ README с постановкой)
├── samples/ sample200.jsonl         канонический sample (n=200, seed=42)
├── scripts/, results/, data_profile/, prompts/, cache/   — этапы 1–2 (canonical)
├── experiments/
│   ├── 00_ПОСТАНОВКА_ЭКСПЕРИМЕНТОВ.md  — единая постановка задачи
│   ├── 01_wikidata_baselines/          пакет этапа 1 (копии)
│   ├── 02_llm_experiments/             пакет этапа 2 (копии)
│   ├── paranames/                      этап 3 (raw 1 GB + индексы)
│   ├── dictionaries/                   этап 4 (4 словаря + raw ~190 MB)
│   ├── stage5_specialized/             этап 5 (5A/5B/5C/5D + модели/кэши)
│   └── stage6_candidate_selection/     этап 6
└── cache/                           общий кэш Wikidata/Wikipedia API (этап 1)
```

## Воспроизводимость

- Все команды в секциях выше; выделенные параметры: seed=42,
  temperature=0.0 (не полностью deterministic — Ollama не гарантирует),
  отчёты с raw-outputs сохранены (JSONL), требования LLM/дампов — в
  `environment.md` + `REPORTS/00_ПОСТАНОВКА_ЭКСПЕРИМЕНТОВ.md`.
- Финальная проверка репозиториев: `git -C ../WikiTableQuestions status --short`,
  `git -C ../wtq-translator status --short`.
