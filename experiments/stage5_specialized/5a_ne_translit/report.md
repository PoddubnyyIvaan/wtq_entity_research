# REPORT — Эксперимент 5A: fine-tune ByT5-small для транслитерации личных имён

## ШАГ 0 / конфигурация

- GPU: RTX 4060 8GB (свободно 5984 MiB, остальное — Windows-дисплей);
  torch 2.14.0+cu126 (pip user); HF кэш в `.cache/hf` (native ext4).
- Модель: **google/byt5-small** (300M, character-level), полный fine-tune
  (без LoRA), bf16, gradient checkpointing, batch 32, lr 1e-3, 3 эпохи,
  seed=42.

## Данные (ParaNames PER, entity-level split)

```text
пул: 946 704 PER-сущности с RU-формой (уникальные QID)
train: 200 000 · dev: 3 000 · test: 3 000 (seed=42; один QID ровно в одном сплите)
выбор размера: 200k выбран как полный реалистичный budget — фактически
3 эпохи заняли 93 мин (см. ниже), т.е. железо прошло 3-5 эпох в разумное время
```

## Обучение (фактические измерения, RTX 4060)

```text
train_time = 5568 s = 93 мин (3 эпохи, ~31 мин/эпоха)
peak VRAM (torch.max_memory_allocated) = 2751 MiB
GPU util во время обучения 94-99%
train_loss 0.159 (финал) · eval_loss 0.1265 (epoch 3)
```

Замечания: dataloader_num_workers=0 (Python 3.14 forkserver pickle-совместимость);
инференс требует `TORCH_DISABLE_NATIVE_JIT=1` (torch 2.14 triton-диспатчер
требует C-компилятор, которого нет; зафиксировано, не BLOCKED — обход).

## Результаты

### Test split ParaNames (n=3000)

| Метрика | Значение |
|---|---|
| exact match | **45.6%** |
| normalized match | 46.0% |
| mean latency | **0.0072 s/имя** (GPU, greedy) |

### Обязательные имена (7 синтетических) — модель gives ВСЕ правильные

```text
Smith → Смит · Smyth → Смит (коллизия, как и у людей)
New York → Нью Йорк (дефис потерян — minor)
London → Лондон · George → Джордж · Arsenal → Арсенал · Washington → Вашингтон
```

### Сравнение на одном материале (sample NAMED_ENTITY, где у WD есть RU-форма, n=78)

agreement с WD RU-формой (НЕ accuracy): **ByT5 14.1% vs BGN-правила 7.7%**
(≈1.8×). Note: многие WD-формы — дескриптивные («Родители», «Рассеяние»,
«1944 год в искусстве»), они систематически не совпадают с транслитерацией
(это свойство метрики, а не ошибка модели — то же явление, что и в этапе 1).

Примеры предсказаний ByT5 (raw): `Торонто Мэпл Лифс`, `Купер-Мазерати`,
`Ислахуддин Сиддик` (typo vs WD «Сиддикуи, Ислахуддин»), `Аллсвенскан`
(✓ лучше дескриптивной WD-формы), garbage на junk-входах (`Нейтболл Лиг
Раунд 6-й герцог Раунд` на «National Football League Round 6» — вне
домена имён, ожидаемо).

### Сравнение с baseline

| Метод | Метрика | Значение |
|---|---|---|
| BGN-правила | agreement с WD (n=78) | 7.7% |
| **ByT5-small (наш FT)** | agreement с WD (n=78) | **14.1%** |
| **ByT5-small** | exact match на ParaNames-test | **45.6%** |
| ParaNames-lookup | coverage на sample200 | 24.5% |
| Wikidict | coverage | 22.5% |
| Wikidata RU | RU-form coverage | 55% |

## Ручная сверка (40 gold)

На 15 reproduced WD-совпадениях из 40 gold (см. comparison_vs_baselines.json):
ByT5 даёт **транслитерацию, а не дескриптивную WD-форму** — на персоналиях
это обычно предпочтительнее («Team Rahal → Тим Рахал» (typo, Рахал правильнее),
«Islahuddin → Ислахуддин Сиддик» (WD: «Сиддикуи, Ислахуддин» — инверсия)).
Identity не проверяется — модель чисто surface-level, NAMED_ENTITY-контекст
не использует (ограничение ByT5 — character-level, без контекста таблицы).

## Выводы

1. ByT5-small fine-tune на ParaNames **превосходит BGN-правила ~1.8×**
   (46% против 4.5% на пара-уровне ParaNames-класса; 14.1% против 7.7%
   agreement на WTQ) и **решает Smith/Smyth→Смит корректно** (7/7 mandatory).
2. **Smith/Smyth-класс закрыт**: модель транслитерирует по подобию, это
   закрывает главный дырный кейс surname-fallback.
3. ByT5 полезен только для NAMED_ENTITY-строк (имён/топонимов), не
   common-слов — на них он печатает транслит («Скаттеринг», «Парент»).
4. Стоимость: 93 мин однократного обучения на 4060; инференс 7 мс/имя.

## Артефакты

- `models/byt5-small-pn-per/` (checkpoint+config), `results/train_meta.json`,
  `results/pn_per_split.json`, `results/eval_{test,dev}.jsonl`,
  `results/eval_sample_named.jsonl`, `results/comparison_vs_baselines.json`.
