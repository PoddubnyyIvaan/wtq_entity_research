# wtq_entity_research — тканиина/справочник команд воспроизведения

Все команды запускаются из `wtq_entity_research/`. Python 3.14, только stdlib + `requests` (user install).

```bash
# профилирование датасета (потоково, без загрузки в память целиком)
timeout 900 python3 -u scripts/profile_wtq.py

# фиксированная стратифицированная выборка 200 (seed=42)
python3 scripts/build_sample.py

# Experiment 0 — copy baseline (локально, без сети)
python3 scripts/exp0_copy.py

# Experiment 2 — Wikidata как entity resolver (rate-limited, кэш в cache/wikidata.json)
timeout 2400 python3 -u scripts/exp2_wikidata.py > results/exp2_run.log 2>&1
# пилот на N примерах: python3 -u scripts/exp2_wikidata.py 20

# Experiment 3 — Wikipedia langlinks vs WD sitelink/label/aliases
timeout 1500 python3 -u scripts/exp3_sources.py > results/exp3_run.log 2>&1

# Experiment 4 — правила транслитерации (локально)
python3 -u scripts/exp4_translit.py

# Experiment 5 — JRC-Names (файл уже в /tmp/opencode в этой сессии; см. report.md секцию 9)
# скачивание: curl -o entities.gzip https://wt-public.emm4u.eu/data/entities.gzip

# Experiment 6 — QC метрики (round-trip, identity, TM consistency)
timeout 2700 python3 -u scripts/exp6_qc.py > results/exp6_run.log 2>&1

# QC decision rules + сверка с ручной разметкой
python3 scripts/exp6b_status.py

# финальная проверка неизменности репозиториев
git -C ../WikiTableQuestions status --short
git -C ../wtq-translator status --short
```

Кэш API: `cache/*.json` (единый JSON-файл). Повторные запуски читают кэш и
повторяют только упавшие (429 и т.п.) запросы.

Ограничения Wikidata/Wikipedia (anonymous): пауза между запросами ≥0.5 s,
backoff при 429 (реализовано в `scripts/common.py::Http`) и `timeout` bash —
все внешние вызовы идут с лимитом времени.


## Этап 2 — LLM-эксперименты (Ollama qwen2.5:3b)

```bash
# сервер (user-space): ~/.local/opt/bin/ollama serve   (модель qwen2.5:3b)
timeout 300 python3 -u scripts/llm_smoke_test.py
timeout 900 python3 -u scripts/exp1_context.py 5 _pilot5      # Pilot 1
timeout 1500 python3 -u scripts/exp1_context.py 20 _pilot20   # Pilot 2
timeout 2400 python3 -u scripts/exp1_context.py 200 ""        # Full 200x4
timeout 1800 python3 -u scripts/exp6_llm_judge.py             # Judge
python3 scripts/mandatory_llm_run.py                          # mandatory cases
```
Результаты: results/exp1_llm_context*.jsonl, results/exp6e_llm_judge.jsonl,
report/llm_experiment_report.md
