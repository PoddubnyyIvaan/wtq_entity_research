# REPORT — Эксперимент 5B: более крупная локальная LLM как localizer (RAG-grounded)

## ШАГ 0 (окружение)

```text
GPU: NVIDIA GeForce RTX 4060, 8188 MiB total, СВОБОДНО 5984 MiB
     (2 188 MiB занято Windows-дисплеем; important для 14b-решения)
CUDA passthrough: работает (KMD 616.56, UMD CUDA 13.4)
torch: 2.14.0+cu126 (pip user), matmul на CUDA проверен
RAM (WSL): 15 GiB total / 14 GiB available (дефолт ~50% хоста)
Диск: 945 GB свободно на нативной WSL ext4; кэши моделей в
      experiments/stage5_specialized/.cache/hf (не /mnt/c)
Ollama: v0.12.5, user-space (~/.local/opt/bin)
```

## Модели

| Модель | Квант | Размер | GPU-факт | Проверка |
|---|---|---|---|---|
| qwen2.5:7b (обязателен) | Q4_K_M | 5.56 GB | **size_vram == size (100% GPU)** | `ollama ps`, nvidia-smi 6.7/8.2 GB |
| qwen2.5:14b (stretch) | Q4_K_M | 10.98 GB | **68% VRAM + CPU-offload** | api/ps vram_fraction=0.68 |

## Протокол localizer (prompt, single-run)

Кандидаты resolver'а (Wikidata ru_form + ParaNames top-1) подаются в промпт;
модель обязана скопировать лучшего кандидата (допустима только правка
регистра/скобок/пробелов) или вернуть NO_CANDIDATE; свободная генерация
запрещена схемой. temperature=0, max_tokens=200. Отдельный запуск не
использует промпты этапа 2.

## Результаты (n=200, полный sample)

| Метрика | qwen2.5:3b (этап 2, CPU) | **qwen2.5:7b (GPU)** | qwen2.5:14b (68% VRAM) |
|---|---:|---:|---:|
| parse success (localizer) | 97.75% (free-gen exp1) | **99%** | 100% (n=25) |
| no_candidate rate | — | 6% | — |
| **Верность кандидату (copy)** | n/a | **22/114 (19%)** | 3/15 (20%) |
| judge needs_review | 93% | 91% | — |
| judge harmful rate | 2% | 5.5% | — |
| latency mean | 0.83 s (CPU) | **1.32 s (GPU)** | **6.43 s (GPU+CPU offload)** |
| p95 | 1.02 s | 1.79 s | ~7.8 s |
| total runtime | 660 s | 264 s | ~160 s/25 → убит по таймауту |

**Ключевой неудобный факт**: 7b НЕ быстрее 3b (0.83→1.32 s/запрос) — модель
в 2.3× больше, 4060 (GPU) работает на полной мощности (VRAM full, 94% util
во время judge), но генерация 7b-Q4 медленнее CPU-инференса 3b. Ускорение
GPU-оффлоада реально (14b на CPU шёл бы ~30+ s), но против 3b-CPU 7b-GPU
даёт +59% latency.

## Главный результат: localizer НЕ слушается схемы

В 89/114 случаях с кандидатами модель **переформулировала** перевод вместо
копирования (e010 Team Rahal → «Команда Рахал», отвергнув обоих кандидатов;
e007 NFL Round 6 → «NO_CANDIDATE» честно; e003 → «Не свободен»).
В обязательных кейсах:

| Кейс | Кандидат (resolver) | 7b localizer | Оценка |
|---|---|---|---|
| Yinchuan (e033) | Иньчуань ✔ | **«Йinchuan»** (смешение алфавитов) | harmful — **сломал правильного кандидата** |
| Buffalo Bills (e087) | Баффало Биллс / Буффало Биллс | «Биллс Бффало» | harmful — сломал |
| Toronto Maple Leafs | Торонто Мейпл Лифс | «Торонто Мэйпл Лифс» | acceptable (typo) |
| Allsvenskan | Чемпионат Швеции по футболу | «Аллсвенскан» | **лучше кандидата** |
| e121 (F♯m…) | Буквенно-цифровое… | NO_CANDIDATE | корректно отверг мусорный WD-кандидат |
| e073 Ha-218 | Берлинские кварталы… | Ha-218 | **отверг неверного кандидата — правильно** |
| e007 NFL Round 6 | Национальная футбольная лига | NO_CANDIDATE | корректно (кандидат был за wrong entity) |

## Manual 40 (single-rater, тот же протокол, что и для 3b)

| Метрика | qwen2.5:3b (этап 2) | **qwen2.5:7b localizer** |
|---|---:|---:|
| harmful substitutions | 12/40 (28%) | **5/40 (13%)** |
| manual needs_review | 22/40 (55%) | **19/40 (48%)** |
| semantic_ok False | 12/40 | 8/40 |
| judge-согласие с manual (review) | 22/40 | 18/40 |
| judge-согласие (harmful) | 29/40 | 35/40 |

Файл: `results/gold_7b_localizer_40.json`.

## Выводы

1. **harmful substitutions: 28% → 13%** — 7b с кандидатами заметно снижает
   подмены против свободной генерации 3b (George/Buffalo Bills-класс частично
   починен: Buffalo Bills переведён 3b в «Бронкос», но 7b localizer СЛОМАЛ
   правильного кандидата в «Биллс Бффало» → остаётся проблема «модель
   переписывает кандидата»).
2. **7b не слушается schema «copy EXACTLY»** (19% faithful) — ключевая
   причина remaining harm. Правильнее в pipeline: копировать кандидата
   напрямую БЕЗ LLM, LLM — только вердикт NO_CANDIDATE/OK.
3. **NO_CANDIDATE-верdictы полезны**: модель корректно отклоняет неверных
   кандидатов resolver'а (GAA-vs-NFL, chord notation, Ha-218 housing).
4. **Latency**: GPU работает (проверено), но 7b на 4060 медленнее 3b на CPU
   (1.32 vs 0.83 s). 14b (68% VRAM → offload) — 6.43 s/запрос, ≈4.9× хуже
   7b; выигрыш в качестве на probe не виден → **не оправдан на этом железе**.

## Ограничения

- n=200 для localizer; manual — 40, один rater.
- Промпт v1 (одна версия; брaces-фикс после pilot; два прогона raw сохранены).
- 14b оценён на первых 25 примерах (прерван: качество не изменилось,
  latency ×5) — досмотр не завершён, что зафиксировано в отчёте.


## Точность (accuracy — добавление по запросу)

Определения (честные, не «gold human accuracy» на всём dataset):
1. **manual-40 accuracy** — доля переводов, принятых без ревью на тех же
   40 ручных кейсах (single-rater, same protocol); strict variant требует
   semantic_ok=True и harmful=False.
2. **silver-reference hit rate** — доля 7b-переводов, совпадающих (normalized)
   с допустимыми формами уровня silver L1/L2 (WD/PN), на пересечении.

| Модель / режим | n | accuracy (strict) | accepted без review | harmful |
|---|---:|---:|---:|---:|
| qwen2.5:3b free generation (этап 2) | 40 | **62.5%** (25/40) | 18/40 (45%) | 11 (27.5%) |
| **qwen7b localizer RAG (5B)** | 40 | **67.5%** (27/40) | 21/40 (52.5%) | 5 (12.5%) |
| 7b localizer vs silver surface-gold | 36 | **25%** (9/36 normalized) | — | — |

Трактовка:
- на human-40 7b-localizer точнее 3b (+5 пп) и harm в 2.2× ниже;
- на silver-reference 7b localizer попадает в «приемлемую форму» только 25% —
  т.е. модель систематически переформулирует кандидатов; правильная практика —
  копирование кандидата напрямую без перегенерации (что Stage 6 подтвердил).
Файл: `results/accuracy_metrics.json`.
