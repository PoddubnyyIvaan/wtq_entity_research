# DATASET_INFO — Statistical EN→RU (KvaytG)

```text
dataset:            en-ru-statistical-dict-20m-corpus (4A) и
                    en-ru-filtered-dict-20m-corpus (4B)
version:            HF main (файл dictionary.parquet; выгружен 2026-09-20)
download/source:    https://huggingface.co/datasets/KvaytG/en-ru-statistical-dict-20m-corpus
                    https://huggingface.co/datasets/KvaytG/en-ru-filtered-dict-20m-corpus
files:              raw/statistical_full.parquet (919 507 B),
                    raw/statistical_filtered.parquet (117 288 B)
format:             Parquet
license:            (на карточке HF; CM, для точности — не проверено в репо README)
entries:            full = 56 624; filtered = 4 096 (count>=1000, probability>=0.5)
fields:             english_word, russian_word, count, probability
notes:              статистическое выравнивание 20M параллельного корпуса;
                    вероятность — это не условная вероятность перевода, а
                    alignment-частота (см. README HF, не заявлено точнее)
```

Локальные индексы: `statistical/cache/index_full.json`, `index_filtered.json`
(normalized_en → [{ru, count, probability}], отсортировано по probability↓).
