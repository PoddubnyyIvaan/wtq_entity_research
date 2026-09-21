# REPORT — Эксперимент 5C: выделенная NMT-модель (NLLB-200-distilled-600M)

## Dataset/model

- `facebook/nllb-200-distilled-600M`, revision `f8d333a098d19b4fd9a8b18f94170487ad3f821d`
  (см. DATASET_INFO.md). **Лицензия CC-BY-NC 4.0 — некоммерческая**.
- eng_Latn → rus_Cyrl, CUDA fp16, beams=4; кэш HF в `.cache/hf` (native ext4).
- Загрузка 167 s; **инференс mean 0.13 s / p95 0.22 s** (GPU; n=23) —
  на порядок быстрее, чем qwen2.5:3b на CPU (0.83 s).

## Подмножество

Только **COMMON_WORD без словарного покрытия** (union 5 словарей = miss):
23 строки (из 48 COMMON_WORD и из 129 без union-покрытия). NAMED_ENTITY не
подавались — **NMT не имеет entity-identity механизма**, зафиксировано как
ограничение.

## Результаты (n=23)

Удачные: «Дома престарелых», «Лучший фильм», «Чрезвычайный и Полномочный
Посол», «История изменений»-класс фразы, «Крыша/Внешняя терраса», «Замок и
ключ» (в кавычках-переводе).

Ошибки/шум:
| Source | NLLB | Оценка |
|---|---|---|
| Modern Hot Records | «Современные горячие записи» | wrong (это чарт-название) |
| Minimum to High | «Минимальный до высокий» | garbled |
| TBD | «ТБД» | должен остаться TBD |
| Brown/White | «Браун/Белый» | цвета прочитаны как имена (identity-ловушка) |
| Nominated | «Номинация» | wrong reading (Result: Nominated) |
| [Data unknown/missing…] | «[Данные неизвестны/потеряются…]» | шаблон переведён — нельзя |
| Busy Doin' Nothin' | «Всё занято, ничего не делаю» | перевод песни, не название |

## Сравнение с qwen2.5:3b на тех же строках (exp1 mode D)

| Строка | NLLB-600M | qwen3b |
|---|---|---|
| Not Free | Не свободно | Не свободен |
| Real-time | **В режиме реального времени** | В реальном времени |
| Best Motion Picture | **Лучший фильм** | Best Motion Picture→(нет/плохо) |
| Nursing Homes | **Дома престарелых** | Дома престарелых(?) |
| Ambassador Extraordinary… | **Чрезвычайный и Полномочный Посол** | — |
| TBD | ТБД (не идеал) | TBD(? ) |

Субъективно (single-rater): NLLB ≥ qwen3b по естественности на длинных
descriptive-фразах; ошибки NLLB — в junk/pseudo-entity строках (TBD,
Brown/White, шаблоны), которые в pipeline должны быть отсечены классом
JUNK/immutable (см. §24 классификацию).

## Выводы

1. NLLB-600M — быстрый (0.13 s) и качественный на **многословных
   descriptive-строках**; заполняет именно ту дыру (35.5%→остальное),
   где словари не работают и где entities не нужны.
2. **Не заменяет entity-пайплайн** (нет identity) — ограничение зафиксировано.
3. Лицензия CC-BY-NC — blocking-параметр для коммерческого использования
   (для research допустимо).

## Метаданные

- `DATASET_INFO.md`: revision, лицензия, инференс-статистика.
- `results/nllb_600m_results.jsonl` (raw), `commonword_no_coverage.json`.


## Точность (accuracy — добавление по запросу)

Manual (single-rater, agent) on n=23 COMMON_WORD без словарного покрытия:

| Метрика | Значение |
|---|---:|
| strict CORRECT | **11/23 = 47.8%** |
| lenient CORRECT+PARTIAL | 18/23 = 78.3% |
| WRONG (identity/шаблон/TBD-cases) | 5/23 = 21.7% |

Это SINGLE-RATER оценка, не team-gold; NAMED_ENTITY строки не оценивались
(не входили в подмножество). Пересечение с 40 human-кейсами: e056, e121,
e182 (частично корректные, но «переводить шаблон/не-сущность» — фильтруемый
класс). Файл: `results/nllb_manual_accuracy.json`.
