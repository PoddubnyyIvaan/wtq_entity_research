# Все эксперименты — единый индекс

Полная постановка задачи (все 4 эксперимента): **`00_ПОСТАНОВКА_ЭКСПЕРИМЕНТОВ.md`**

```text
experiments/
├── 00_ПОСТАНОВКА_ЭКСПЕРИМЕНТОВ.md   ← единая постановка задачи
├── 01_wikidata_baselines/           ← Эксперимент 1 (без LLM)
│   ├── data_profile/                профилирование WTQ
│   ├── samples/                     копия sample200 (canonical: ../../samples/)
│   ├── results/                     exp0 copy, exp2 Wikidata, exp3 источники,
│   │                                exp4 транслит, exp6 QC, exp6b статусы,
│   │                                gold_manual.json, summary_metrics.json
│   ├── scripts/                     profile_wtq, build_sample, exp0/exp2/exp3/
│   │                                exp4/exp6/exp6b
│   └── report.md                    отчёт этапа 1 (+ ответы на 12 вопросов)
│
├── 02_llm_experiments/              ← Эксперимент 2 (Ollama qwen2.5:3b)
│   ├── prompts/                     exp1_v1.txt, exp1_v2.txt, judge_v1.txt
│   ├── results/                     exp1 200×4 (raw+stats), pilot5/pilot20,
│   │                                exp6e judge, exp6b статусы, gold_*_40,
│   │                                mandatory_llm, smoke test
│   ├── scripts/                     llm_smoke_test, exp1_context, exp6_llm_judge
│   └── llm_experiment_report.md     отчёт этапа 2 (Q1–Q12)
│
├── paranames/                       ← Эксперимент 3 (каноническое расположение)
│   ├── DATASET_INFO.md, PARANAMES_REPORT.md
│   ├── paranames_results.jsonl, sample_200.jsonl
│   ├── scripts/ (6), cache/ (индексы), raw/ (paranames.tsv.gz ~1 GB)
│   └── results_40cases.json, results_rerank.json, results/stats.json
│
└── dictionaries/                    ← Эксперимент 4 (каноническое расположение)
    ├── wikidict/ · wiktionary/ · openrussian/ · statistical/
    │   ├── DATASET_INFO.md, REPORT.md, results*.jsonl, sample_200.jsonl
    │   ├── scripts/, cache/, raw/
    ├── scripts/ (common_dict, compare_analyze, rerank_candidates)
    ├── COMPARISON_REPORT.md         сравнение 5 словарных прогонов + ответы §25
    ├── COMPARISON_ANALYSIS.json, manual40_candidates.json, rerank_results.json
    └── (raw данные ~190 MB)
```

## Порядок чтения

1. `00_ПОСТАНОВКА_ЭКСПЕРИМЕНТОВ.md` — цели, данные, ограничения, метрики.
2. `01_wikidata_baselines/report.md` — базовые числа: WD RU-coverage 55%,
   identity 34.8%, rule-QC 51% review, round-trip 5.4%.
3. `02_llm_experiments/llm_experiment_report.md` — qwen2.5:3b: parse 97.75%,
   mean 0.83 s; harmful substitutions ≈28%; judge needs_review 93% (шум).
4. `paranames/PARANAMES_REPORT.md` — PN coverage 24.5%, QID-путь 52% форм;
   hybrid-стратегия.
5. `dictionaries/COMPARISON_REPORT.md` — словари 6–22.5%, union 35.5%,
   agreement ≥0.93 (лексические пары) как confidence-сигнал.

## Примечание о расположении файлов

- `paranames/` и `dictionaries/` — исходные рабочие директории (не перемещены,
  чтобы не ломать документированные пути в их скриптах/отчётах).
- `01_*` и `02_*` — собранные пакеты этапов 1–2 (копии соответствующих
  артефактов из корня `wtq_entity_research/`); живые копии скриптов, на
  которые ссылаются документы этапов, лежат там же — оригиналы в корне
  (`scripts/`, `results/`, `prompts/`) сохранены для совместимости
  cross-экспериментных путей (paranames/dictionaries читают
  `../results/exp2_*.jsonl` из корня).
- Общий кэш API-запросов Wikidata/Wikipedia: `../../cache/` (корень).
