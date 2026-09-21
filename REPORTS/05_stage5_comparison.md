# COMPARISON_REPORT — Этап 5: специализированные модели (5A–5D) на RTX 4060

Baseline этапов 1–4 (один sample, n=200; не «accuracy»):
WD RU-form coverage 55% · identity verified 34.8% · rule-QC review 51%,
rule/manual 30/40 strict · round-trip 5.4% · ParaNames 24.5% ·
словари (union) 35.5% · qwen2.5:3b free-gen harmful 28% · judge 22/40.

## Железо (ШАГ 0, зафиксировано)

```text
GPU: RTX 4060 8GB — фактически свободно 5984 MiB (Windows display 2 GB)
torch 2.14.0+cu126 (pip user), CUDA passthrough работает
Ollama: 7b Q4_K_M = 100% GPU (5.56 GB); 14b = 68% VRAM + CPU offload
RAM (WSL): 15 GiB (дефолт ~50%; если нужен 14b+ — править .wslconfig)
Диск: 945 GB (native ext4); кэши моделей: experiments/stage5_specialized/.cache/
```

## Сводная таблица

| Подход | Coverage / аудит | Качество (на 40 gold / измеренных) | Identity | Harmful | Latency (RTX 4060) | Роль |
|---|---|---|---|---|---|---|
| **5A ByT5-small FT** (ParaNames PER 200k, 93 мин train, peak 2.7 GB) | 100% генерации (domain: имена) | test exact **45.6%**; agreement с WD 14.1% (BGN 7.7%); **7/7 mandatory Smith/Smyth-класс** | нет (surface) | низкая на имена | **7 ms/имя** | surname-fallback (закрывает Smith/Smyth) |
| **5B qwen2.5:7b localizer** (GPU, RAG-кандидаты) | 114/200 с кандидатами | harmful **5/40 (13%)** vs 3b 28%; review 48%; но **верность кандидату 19%** — переписывает | через кандидата | ↓ 28%→13% | **1.32 s/запрос** (медленнее 3b-CPU 0.83 s!) | доп-валидация/отклонение кандидатов (NO_CANDIDATE) |
| 5B qwen2.5:14b (stretch) | 68% VRAM offload | parse 100%, faithful 3/15 | — | — | **6.43 s/запрос** | **не оправдан** на 8 GB |
| **5C NLLB-600M** (CC-BY-NC) | 23/23 COMMON_WORD без словарей | естественные фразы («Дома престарелых», «Чрезвычайный и Полномочный Посол»); ошибки на junk/TBD/шаблонах | нет (explicit) | ограничено class-фильтром | **0.13 s/запрос** | descriptive-строки после junk-фильтра |
| **5D QC-классификатор** (GBM, LOO n=40) | — | **65%** vs rule 55% vs judge 55% (не значимо при n=40) | — | — | ms | proof-of-concept; фичи дешевле judge |

## Явные ответы

**Что включать в production-архитектуру wtq-translator:**

1. **5A (ByT5 транслитерация) — ДА.** Закрывает Smith/Smyth-класс (7/7),
   1.8× лучше правил, 7 мс/имя, 93 мин однократного обучения, полностью
   воспроизводимо. Роль: surname/name fallback после ParaNames/Wikidata.
   Не применять к common-words (печатает транслит) — только NAMED_ENTITY.
2. **5C (NLLB-600M) — ДА** для descriptive-многословных строк без словарного
   покрытия (0.13 s, качество ≥ qwen3b), с обязательным class-фильтром
   (JUNK/immutable/шаблоны не подавать). Ограничение: лицензия CC-BY-NC.
3. **5B (7b как localizer) — ограниченно**: выгоден только NO_CANDIDATE-
   вердикт (отклоняет неверных кандидатов resolver'а — 6% + верные отказы
   на GAA/chord/Ha-218). Но: модель переписывает кандидата в 81% случаев,
   и GPU-7b МЕДЛЕННЕЕ CPU-3b на 4060. Если LLM вообще включать в pipeline —
   не для генерации, а только для вердикта; генерацию заменять
   детерминированной копией кандидата.
   **14b — НЕТ** (68% offload, 4.9× latency, качество не лучше на probe).
4. **5D — НЕ как модель**, а как идея: rule-based сигналы (stratum, ambiguous
   flag, PN match) уже дают 65% при n=40; self-reported LLM confidence не
   полезен. Production: расширять human gold, пока — rule-based QC.

**GPU-бюджет для будущих экспериментов на этом железе** (замерено):
ByT5-small FT ≈ 31 мин/эпоха (200k пар, batch 32, 2.7 GB VRAM);
NLLB-600M инференс 0.13 s/строка; qwen7b-GPU 1.3 s/запрос (200 items ≈ 4.5 мин);
qwen14b offload 6.4 s/запрос.

## Ограничения этапа

- 5A/5B/5C не смешивались до этого сравнения; manual gold — 40 (один rater).
- 5B 14b probe прерван на 25/200 (качество без изменений при ×5 latency —
  зафиксировано, не имитировано).
- Все agreement-числа — с WD/ParaNames формами, не accuracy; human gold —
  только 40 reused cases.
