# DATASET_INFO — Wikidict EN→RU

```text
dataset:            wikidict-dsl-ru (Wikidata Bilingual DSL Dictionaries, Russian)
version/commit:     master, 1 commit (2022+); файл данных выгружен 2026-09-20
download/source:    https://github.com/open-dsl-dict/wikidict-dsl-ru
file:               data/en-ru_wikidict.dsl → raw/en-ru_wikidict.dsl
size:               76 761 649 bytes (UTF-8)
format:             ABBYY Lingvo DSL (UTF-8); пары "headword / RU-строка / [m1]-карточки"
license:            CC0 (данные Wikidata)
entries (README):   628 522 (en-ru)
index keys:         564 368 normalized EN heads (наш индекс: headword → RU-строка)
fields:             RU-строка (перевод, часто дискриптивный), карточка без POS
notes:              фактически это Wikidata/interwiki titles — т.е. EN canonical
                    surface → RU canonical surface; без POS/senses/frequency
```

Локальный индекс: `wikidict/cache/index.json` (dict: normalized_en → [{ru, card}]).
