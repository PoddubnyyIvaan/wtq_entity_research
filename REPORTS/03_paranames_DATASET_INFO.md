# DATASET_INFO — ParaNames (официальные метаданные)

```text
dataset:            ParaNames 1.0 (parallel entity names)
version:            v2024.05.07.0 (GitHub release, 2024-05-07)
download/source:    https://github.com/bltlab/paranames/releases/tag/v2024.05.07.0
                    (asset: paranames.tsv.gz, 999 401 108 байт, скачан 2026-09-20)
source Wikidata dump: latest-all.json.bz2, 2024-03-13 11:18, bytes 87 292 717 562,
                    SHA256 d1de7ee6da99656be7bc72ef90bc0ef8
languages:          400+ (полный список в файле)
English language code:  en
Russian language code:  ru
file(s) used:       raw/paranames.tsv.gz (см. конфигурацию в скриптах build_index.py)
format:             TSV, header: wikidata_id | eng | label | language | type
                    type ∈ {PER, LOC, ORG}
                    (одна строка = (сущность, язык, имя-в-этом-языке); не ISO, без score/freq)
number of records:  ~78 млн строк (по метаданным HuggingFace-фикса
                    imvladikon/paranames, который обработан из этого же релиза);
                    точное число посчитано скриптом build_index.py при
                    поточном проходе → coverage_stats.json «total_records»
license:            MIT (репозиторий bltlab/paranames)
paper:              Sälevä & Lignos, LREC-COLING 2024 (arXiv:2405.09496)
caveats:            повторяющиеся wikidata_id между строками = multi-type entities;
                    языковая фильтрация по умолчанию отсутствует;
                    поле `type` — всего 3 базовых класса
```

## Путь к локальному файлу

`wtq_entity_research/experiments/paranames/raw/paranames.tsv.gz` — не копируется
в output; все скрипты читают его по этому пути (см. build_index.py).

## Полезные поля для эксперимента

| Поле        | Содержание |
|-------------|-----------|
| wikidata_id | QID сущности — используется для identity-проверки с Wikidata |
| eng         | английское имя (canonical, из Wikidata label) |
| label       | имя на языке `language` |
| language    | код языка (Wikipedia/Wikidata ISO, например ru/en) |
| type        | PER / LOC / ORG |

Нет полей frequency/confidence/source — в этой версии их не предусмотрено
(см. paper: фильтрация сделана на этапе генерации).
