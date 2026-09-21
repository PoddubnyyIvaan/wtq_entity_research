# DATASET_INFO — Wiktionary EN→RU

```text
dataset:            wiktionary-dict (Open DSL Dictionary Project)
version:            master (1 commit); файл выгружен 2026-09-20
download/source:    https://github.com/open-dsl-dict/wiktionary-dict
file:               dsl/oneway/en-ru-enwiktionary.dsl.dz → raw/en-ru-enwiktionary.dsl.dz
size:               3 282 135 bytes (dictzip-gzip, UTF-16 внутри)
format:             DSL (UTF-16), односторонний EN→RU
license:            CC BY-SA 3.0 + GFDL (двойная; как оригинал Wiktionary)
entries:            ~261 000 строк DSL (прибл. 35-40 тыс. словарных статей)
index:              1 261 ключей EN → 5 235 RU-кандидатов с {pos, sense}
fields:             headword, POS (<n>, <v>, <m>, <f>, <adj>…), sense — английский
                    глоcc из [i](…)[/i], RU-переводы из [m1]/[m2]-карточек,
                    произношение отброшено, **multiple senses сохранены**
raw Wiktionary dump: НЕ скачивался (~2.7 GB gzip / 23.5 GB JSONL) — готового
                    en-ru словаря достаточно (см. условие эксперимента)
```

Локальный индекс: `wiktionary/cache/index.json` (normalized_en → [{ru, pos, sense}]).
