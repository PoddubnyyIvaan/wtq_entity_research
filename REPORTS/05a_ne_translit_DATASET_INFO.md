# DATASET_INFO — 5A (train split)

```text
model:             google/byt5-small (300M, character-level)
fine-tune:         полный (без LoRA/PEFT), bf16, gradient checkpointing
train source:      ParaNames 1.0 PER-сущности (см. experiments/paranames/DATASET_INFO.md)
pool:              946 704 PER-сущностей с RU-формой (уникальные QID)
split:             train 200 000 · dev 3 000 · test 3 000, seed=42,
                   entity-level (QID ровно в одном сплите)
                   фактическое время эпохи: ~31 мин на RTX 4060 → 3 эпохи
                   за 93 мин; сэмпл НЕ занижен (200k за разумное время)
optimizer/lr:      lr 1e-3, batch 32, 3 эпохи
peak VRAM:         2751 MiB (torch.max_memory_allocated), GPU util 94-99%
device:            NVIDIA GeForce RTX 4060 (free VRAM на старте 5984 MiB)
cache path:        experiments/stage5_specialized/.cache/hf (native ext4)
checkpoint:        experiments/stage5_specialized/5a_ne_translit/models/byt5-small-pn-per/
известные обходы:  dataloader_num_workers=0 (Python 3.14 forkserver),
                   TORCH_DISABLE_NATIVE_JIT=1 для generate (нет gcc в WSL)
```
