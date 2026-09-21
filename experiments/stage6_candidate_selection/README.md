# Stage 6 — Candidate-Constrained Entity Selection (README)

Гипотеза: запрет генерации entity surface у LLM + выбор из candidate set +
детерминированный COPY снижает harmful substitutions.

## Запуск (воспроизводимость)

```bash
cd experiments/stage6_candidate_selection

# 1) candidate sets + silver labels (из существующих артефактов этапов 1–5)
python3 scripts/build_sets.py

# 2) детерминированные baselines + feature reranker + oracle set
python3 -u scripts/baselines_and_oracle.py oracle
python3 -u scripts/baselines_and_oracle.py baselines
python3 -u scripts/baselines_and_oracle.py feature_reranker

# 3) LLM selection (NO generation; prompt stage6_v2; temperature=0, max_tokens=120)
python3 -u scripts/run_llm_selection.py qwen2.5:7b D main     # mode D, n=116
python3 -u scripts/run_llm_selection.py qwen2.5:3b D main
for M in A B C E; do python3 -u scripts/run_llm_selection.py qwen2.5:7b $M abl7b; done
for M in A B C;  do python3 -u scripts/run_llm_selection.py qwen2.5:3b $M abl3b; done

# 4) oracle reruns + shuffled-context control (n=50)
python3 -u scripts/run_oracle.py
python3 -u scripts/run_llm_selection.py qwen2.5:7b D shuffled shuffled_ids.json
python3 -u scripts/run_llm_selection.py qwen2.5:3b D shuffled shuffled_ids.json

# 5) оценка + таблицы
python3 -u scripts/evaluate.py
```

## Параметры (§22)

```text
sample: sample200.jsonl (n=200, seed=42; dev e001–e020, eval e021–e200)
models: qwen2.5:3b (CPU, ollama v0.12.5), qwen2.5:7b (GPU RTX 4060, Q4_K_M)
temperature 0.0, max_tokens 120
candidate sources: Wikidata (sitelink/label/aliases по QID из exp3), ParaNames
                   (stage-3 results); provenance сохранена
candidate ids:     candidate_NN (переформатированы с c_NN после v1-прогона:
                   модели систематически возвращали "candidate_XX" по примеру
                   в промпте — это исправление схемы ID, не модели)
prompt versions:   stage6_v1 → stage6_v2 (единственная разрешённая итерация:
                   литерал "<candidate_id>|NO_MATCH" из v1 копировался моделями;
                   + детерминированная нормализация {{}}-braces артефакта)
hardware:          RTX 4060 8GB (free 5984 MiB), 15 GiB WSL RAM
LLM runs:          7b: 116 (main) + 464 (ablation) + 116 (oracle) + 50 (shuffled)
                   3b: 116 + 348 + 116 + 50
runtime:           ~30 min total LLM; deterministic — секунды
```

## Файлы

```text
candidate_sets.jsonl    200 строк: candidates с provenance (qid, source, score)
silver_labels.jsonl     silver labels (levels 0-4; identity/surface раздельно;
                        ambiguous/unknown исключены из labeled-метрик отдельно)
selection_results.jsonl детерминированные выборы (B0/B1/B2)
metrics.json            все метрики (retrieval/selection/oracle/shuffled/
                        ablation/safety/human40)
analysis.md             главный отчёт (структура §23)
tables/                 retrieval.csv, selection.csv, by_stratum.csv,
                        context_ablation.csv, oracle.csv, safety.csv
raw/qwen3b/, raw/qwen7b/  raw LLM outputs по тегам
oracle_sets.jsonl       ORACLE candidate sets (gold добавлен 0 раз —
                        gold form всегда уже была в candidate set)
shuffled_ids.json, shuffled_map.json  negative-control материалы
b2_feature_importance.json
```

## Ограничения

- silver построен из тех же resolver-форм, что и candidate set →
  B0/reranker agreement на silver circular; human-40 — единственная
  leakage-free проверка (25/40 attempted).
- 84/200 примеров без кандидатов исключены из selection-метрик (только
  NO_MATCH coverage).
- ЛЛМ-итерація промпта одна (v1→v2); raw v1 сохранён.
