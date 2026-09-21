# DATASET_INFO — OpenRussian EN→RU

```text
dataset:            OpenRussian.org dictionary data (Badestrand/russian-dictionary)
version:            GitHub master (public backup CSVs, "a bit outdated" — по README)
download/source:    https://github.com/Badestrand/russian-dictionary
                    (официальный репозиторий данных OpenRussian.org;
                    актуальная полная база также доступна через TogetherDB,
                    но ссылка на прямой dump с сайта dictionary-data не публикуется)
files:              nouns.csv (8.4 MB), verbs.csv (5.7 MB), adjectives.csv (8.4 MB),
                    others.csv (344 KB) — в raw/
format:             TSV (разделитель TAB): bare, accented, translations_en,
                    translations_de, POS/падежные формы и т.д.
license:            CC BY-SA 4.0
entries:            45 328 ключей EN → суммарно RU-слов
fields:             bare (RU слово без ударений), accented (с ударением),
                    translations_en (английские глоссы, часто списком через , ; /),
                    POS/гендер/склонения (для noun/verb/adj)
usage:              обратный индекс: EN gloss → RU word; 'с ударениями' сохранено
                    в поле accented (в отчёте не используется)
```

Локальный индекс: `openrussian/cache/index.json` (normalized_en_gloss → [{ru}]).
