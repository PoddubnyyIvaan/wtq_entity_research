# environment.md

## Commit hashes (без изменений за всё исследование)

```text
WikiTableQuestions  HEAD = 7d455a5a707b96341ef72aff9428749d443d8aa9   (clean)
wtq-translator      HEAD = 7691197ecb0e968865e7f3905586bae156802910   (untracked .idea/ уже существовал до работы)
```

## Дата экспериментов
2026-09-18 … 2026-09-19 (UTC+08:00)

## Окружение
- OS: Linux (WSL2), Python 3.14.4 (system)
- Библиотеки: `requests 2.32.5` (зачем — только как транзитивно доступный HTTP; основные скрипты используют stdlib urllib)
- Seed: 42 (фиксированный, во всех скриптах, где есть рандом)
- Виртуальное окружение: не используется; `pip install --user --break-system-packages requests` в общий user-site (не в репозитории)

## Внешние endpoints
| Endpoint | Назначение |
|---|---|
| https://www.wikidata.org/w/api.php | wbsearchentities (en/ru), wbgetentities (labels/aliases/sitelinks/claims) |
| https://en.wikipedia.org/w/api.php | action=query list=search (fallback), prop=langlinks |
| https://wt-public.emm4u.eu/data/entities.gzip | JRC-Names entity/variants file (14.2 MB gzip, ≈3.4 GB распакованный) — проверка доступности; полный разбор потоком |
| https://joint-research-centre.ec.europa.eu/language-technology-resources/jrc-names_en | оф. страница JRC-Names |
| https://data.europa.eu (data portal API) | JRC-Names метаданные (distributions partly dead) |
| op.europa.eu / datahub.io | проверены: dead/redirect |

## Rate limits
Wikidata/Wikipedia anonymous API: интервал ≥0.55 s, адаптивный backoff при 429
(до 4 s пауза между запросами, 3–6–12 s retry). Нарушение наблюдалось: серии
429 без backoff ломают ран.

## Использованные модели (LLM) — обновлено после установки Ollama
- Эксперимент 1 (контекстные режимы A–D): ВЫПОЛНЕН (Этап 2, см. report/llm_experiment_report.md)
- Эксперимент 6E (LLM judge): ВЫПОЛНЕН (Этап 2)
- Модель: **qwen2.5:3b** (Ollama), family=qwen2, VRAM-резидент 2.9 GB, CPU inference (12 cores, 15 GiB RAM, no GPU)
- Ollama сервер: v0.12.5, user-space установка ~/.local/opt, порт 11434; модель хранится в ~/.local/ollama/models
- Endpoint: http://localhost:11434/v1 (OpenAI-compatible /chat/completions), API key фиктивный (локальный)
- Параметры: temperature=0.0, max_tokens=350 (exp1) / 350 (judge); **seed не поддерживается Ollama chat API данным путём** —
  вывод не гарантированно deterministic (temperature=0 снижает, но не устраняет различия; см. #22 задания)
- latency: exp1 mean 0.83 s / p95 1.02 s на запрос; judge mean 0.93 s / p95 1.3 s; всего ~11 мин (exp1 800 req) + 3 мин (judge 200 req)
- Первый smoke-тест выявил баг prompt_v1 (модель отвечала на вопрос и выводила китайский при context); переписан в prompt_v2 — обе версии сохранены в prompts/.
- Все 3 поля выборки, промпты, raw responses, метрики и оценки сохранены; ручные вердикты для LLM-переводов отдельно: results/gold_llm_translations_40.json

## Первичная NER
Использована существующая CoreNLP 3.5.2 разметка `tagged/*-tagged/*.tagged`
(поля nerTags/nerValues). Свой NER не запускался.

## Известные ограничения
1. Нет LLM ⇒ Experiment 1 (A–D контекстные режимы), E-branch decision rules,
   LLM-judge — не запускались; результаты намеренно не имитировались.
2. Выборка стратифицирована, но каждый стратум мал (10–30) ⇒ малые статистики.
3. "Human" контроль — 40 примеров, один разметчик (агент-исследователь),
   основанный на данных Wikidata descriptions и здравом смысле — не gold
   standard в строгом смысле.
4. Обратный поиск (identity) выполнен только для 60 RU-форм из 104
   (subsample, seed=42) из-за rate limits Wikidata.
5. Non-Latin скрипты в ячейках (397 кириллических значений в таблицах WTQ,
   иврит и др.) исключены из выборки и не покрыты цифрами.
6. timing: фиксировался только wall-clock (≈15–25 мин на 200 ячеек c
   троттлингом); аккуратного per-item timing нет.
7. JRC-Names jam-file разобран поточно, но только макро-статистика: файл
   ~3.4 GB распакованный, полный парс не сохранён на диск.
