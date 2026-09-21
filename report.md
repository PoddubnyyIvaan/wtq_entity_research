# Исследование перевода именованных сущностей WikiTableQuestions (EN → RU)

Дата: 2026-09-18/19 · выборка: 200 (seed 42) · репозитории не изменены
(WikiTableQuestions `7d455a5`, wtq-translator `7691197`)

---

## 1. Executive summary

- **Wikidata не «резиновый» источник, но обязательный.** При голосовании
  `wbsearchentities → Wikipedia fallback` candidate coverage 97.5%, но RU-форма
  найдена только для **56%** ячеек, а из них **~20% предложений неверны**
  (error по ручной проверке). Wikidata полезна как **resolver + validator** и
  только частично как переводчик.
- **Round-trip EN→RU→EN exact match подтверждён как ненадёжная метрика в обе
  стороны:** 6/112 RU-форм совпадают с source (т.е. правильные переводы
  «Лондон/Иньчуань» падают), и всё же есть случаи, когда round-trip проходит,
  а перевод неверный (`current → течение`).
- **Простые правила транслитерации не пригодны как основной механизм**
  (совпадение с Wikidata-формами 4.5% на уверенном подмножестве); пригодны
  только с традиционным словарём и только для поверхностной генерации, а не
  для выбора правильной формы.
- **JRC-Names доступен и жив** (файл ~3.4GB распакованный), но покрывает
  **только persons + organisations**, кириллических вариантов 5.6%, локации —
  отсутствуют. Как fallback для персоналий — возможен; как основной — нет.
- **Минимальный рабочий контекст для резолва:** значение + header колонки +
  строка таблицы (вопрос WTQ и page title полезны, но не заменяют header/row).
- **Rule-based QC даёт manual-review rate 51%;** по ручной разметке 40 примеров
  ужесточение снижает необходимость ручной проверки, а рекомендуемое
  «рабочее» правило (identity ≥0.9 либо clean RU sitelink + одна совпадающая
  строка контекста) требует ручной проверки ~20–25%.

---

## 2. Что находится в WikiTableQuestions

Потоково (без чтения файлов целиком в LLM):

| Параметр | Значение |
|---|---|
| вопросов (тренировка + 2 pristine) | 14 149 + 4 344 + 3 516 = **22 009** |
| уникальных таблиц | **2108** |
| ячеек | **376 917** |
| строк на таблицу (ср. / min / max) | 27.5 / 4 / 753 |
| колонок на таблицу (ср.) | 6.4 |
| empty | 20 695 (5.5%) |
| numbers/dates/pct | 103 424 + 17 958 + 2 440 (33.6%) |
| прочие строковые | **218 558 (58%)** |
| из них cyrillic в исходнике | 397 |
| уникальных строковых значений (<60 симв.) | **104 396** на 213 979 ячеек |
| повторяются между таблицами | 17.7% уникальных значений |
| топ-заголовки | Year (430), Date (378), Notes (298), Name (268), Opponent (163), Location (150), Team (118), … |
| CoreNLP NER в ячейках (сэмпл ~23k токенов) | NUMBER 9 958, PERSON 4 483, DATE 3 753, **LOCATION 3 282, ORGANIZATION 1 269, MISC 931** |

Источник: `results/.data_profile/wtq_profile.json`, `scripts/profile_wtq.py`.

**Доступная NER-разметка достаточно полная** для адресации PERSON/LOCATION/
ORGANIZATION и выпадения общих слов; но шум: `Fashion Magazine→LOCATION`,
`Leo→PERSON`, `Cooper-Maserati→SURNAME` — брак есть, поэтому выборка строилась
по правилам, скомбинировавшим NER + колонку-заголовок.

`page/<N>-page/<M>.json` содержит только `title/url/tableIndex/hashcode/id/
revision`, контекст страницы — сам HTML (`M.html`, ~80 КБ на таблицу);
для entity resolution в экспериментах использовалась `title` page (в 100% случаев
заполнена) и структурные captions/columns.

---

## 3. Метод формирования выборки

`scripts/build_sample.py`, seed=42, квоты:

```
PERSON 30 · SURNAME 15 · LOCATION 25 · ORGANIZATION 20 · SPORTS_TEAM 20
EVENT_WORK 25 · MULTI_WORD 20 · SHORT_AMBIGUOUS 20 · FALSE_POSITIVE 15 · UNKNOWN 10
```

- Источник кандидатов: **все существующие CoreNLP-отмеченные** ячейки из
  2108 таблиц (skip чисел/дат/процентов/длинных/не-Latin/шаблонного мусора).
- Примерный pool до квотирования (штук): LOCATION 85k, PERSON 22k,
  UNKNOWN 23k, ORGANIZATION 12k, SHORT_AMBIGUOUS 9k, FALSE_POSITIVE 8.5k,
  SURNAME 3.5k, MULTI_WORD 3.5k, EVENT_WORK 1.4k, SPORTS_TEAM 0.9k
  (`samples/pool_stats.json`).
- Каждый пример хранит: cell value, header, соседние ячейки той же строки,
  table caption/title, page title/url/tableIndex, вопрос WTQ (если есть),
  stratum, location, NER-теги.
- 160/200 имеют вопрос, привязанный к таблице.
- dev: `e001–e020`, eval: `e021–e200` — eval не использовался для тюнинга
  эвристик резолвера (эвристики были написаны до запуска на eval; случайные
  отклонения только корректировали BUG-фиксы, не качество).

**Обязательные синтетические кейсы** хранятся отдельно
(`samples/mandatory_cases.json`) и в общую статистику WTQ не попадают.

---

## 4. Experiment 0 — Copy / Identity baseline

`results/exp0_copy.jsonl`:

```text
n = 200; identity_preserved = 100%  ·  RU form = 0%  ·  latin_share = 100%
```

Copy оставляет неизменной identity (это контроль), но для RU-датасета все
100% ячеек останутся на латинице — **изменение surface form оправданно**,
иначе перевод мало что даёт. Следствие: копия как fallback допустима только
для immutable-значений (`728i`, `N/A`, `Ha-218`, `Ж2/РУС/XB`, числа-диапазоны и
т.п.) и временно для «no_translation_flaggable» узлов.

---

## 5. Experiment 1 — Влияние контекста (A–D) — **BLOCKED**

**Причина**: нет LLM API (нет ключей в env, нет ollama, нет локальных моделей).
`wtq-translator` не запускался не только из-за запрета, но из-за отсутствия
API (`base_url http://localhost:11434/v1` из его конфига — упал).

**Зафиксированное требование для продолжения:**
1. любой OpenAI-compatible endpoint (base_url + api_key + model_name);
2. или локальный ollama с моделью ≥ ~2B;
3. budget: примерно 4 режима × 200 ячеек ≈ 800 запросов + 5-мерный judge
   (Experiment 6/E) ≈ 400 запросов. Всего ~1200 коротких запросов.

**Что сделано вместо:** качественные кейсы, показывающие необходимость
контекста для резолвинга (case study: «National Football League Round 6»
(ср. §11), `@ Giants`) — и количественно: в evaluation sample 93/200 получили
флаг `multiple plausible QIDs`, 43/200 `low string match` (нужны для
контекстного ранжирования).

---

## 6. Experiment 2 — Wikidata как Entity Resolver

`results/exp2_wikidata.jsonl`, `exp2_wikidata_stats.json`.

**Пайплайн**: очистка значения → `wbsearchentities(en)` → fallback
`en.wikipedia list=search → pageprops wikibase_item` → оценка кандидатов
(string sim на label/alias + штраф за disambiguation page + bonus за
совпадение P31 с expected type из header) → details `wbgetentities` → RU
форма: `ru_sitelink > ru_label > ru_alias` (латиница помечается, не элиминируется).

| Метрика ⎜ n=200 | Значение |
|---|---|
| candidate coverage (QID найден) | **0.975** |
| RU-form coverage | **0.560** (sitelink 84, label 19, alias 4, latin 5) |
| флаг: multiple plausible QIDs | 93 |
| флаг: no candidates | 5 |
| флаг: RU form is Latin | 19 |
| флаг: low string match (fallback noise) | 43 |

**Wikipedia fallback** существенен: после чистого `wbsearchentities` coverage
был 0.735; падает это «low string match» 43 — страница Википедии находится
даже когда сущность не в WB-индексе.

**Ключевые наблюдения:**
- Верное identity + хорошая RU форма есть для локаций/людей/клубов
  (Yinchuan→Иньчуань, Toronto Maple Leafs→Торонто Мейпл Лифс, Buffalo Bills→
  Баффало Биллс, Michael Andretti→Андретти, Майкл).
- **Harmful suggestions при naive top-1**: `Fashion Magazine → журнал мод`,
  `Student/Model → adaptive learning`, `7ZL → Australian Walkabout`,
  `@ Giants → Гиганты` (греч. мифология), `Ha-218 → Берлинские кварталы…`.
  Без контекстного ранжирования P31+header часть пропускает мимо.
- WD RU label часто **описывает, а не называет**: `Allsvenskan → Чемпионат
  Швеции по футболу` — identity сохранена, но RU чтение менее «собственное».

---

## 7. Experiment 3 — Wikipedia langlinks vs Wikidata sources

`results/exp3_sources.jsonl`, `exp3_sources_stats.json` (n=195 QID-linked):

| Источник | coverage | cyrillic clean | latin | служебные «(значения)»-style |
|---|---|---|---|---|
| ru sitelink title (WD) | 43.6% | 54 | 14 | 17 |
| Wikipedia langlinks | 43.6% | 53 | 14 | 18 |
| ru label (WD) | **57.9%** | **86** | 27 | 0 |
| ru aliases | 31.8% | 41 | 21 | 0 |

- **langlinks ≡ ru sitelink** (agreement 100%) — использовать оба смысла нет.
- **ru label шире sitelink** (+28 pp) и попадает при отсутствии ru-статьи,
  но содержит 27 латиниц и 17 служебных уточнений (в sitelink).
- **aliases редко добавляют новое** (.alias_needed = 0), но покрывают 41
  cyrillic; как hint полезны когда и sitelink, и label в латинице/empty
  одновременно — таких случаев 0 в этом подмножестве (объединить нужно с
  данных langlinks только 13 «langlinks_only»).
- Sitelink добавляет «подпись статьи» — там появляются хвосты `(значения)`,
  `(аэропорт)` для склейки РУ форм.

---

## 8. Experiment 4 — Транслитерация и правила

`scripts/exp4_translit.py`, `results/exp4_translit_stats.json`.

Оценка только по «уверенному» подмножеству: score ≥0.9, нет flags на
неоднозначность, WD RU присутствует (n=**22** — мала, осторожно):
- чистые BGN-подобные правила: **согласование 4.5%** — в основном дают,
  правила дают формы с ошибками (`Нев Йорк`, `Дорд`).
- с добавкой традиционного образования (авто-словарь на 60 слов) все
  мерыные обязательные кейсы проходят: `New York→Нью-Йорк`, `London→Лондон`,
  `George→Джордж`, `Arsenal→Арсенал`, `Washington→Вашингтон`,
  `Smith/Smyth→Смит (коллизия!)`.
- вывод: правила пригодны только как **fallback для одиночных персоналий**
  при наличии (i) словаря традиционных форм и (ii) флага `transliteration_
  collision` для Smith/Smyth-класса. Для организаций/команд правила
  не пригодны (multi-word, смешанные language, редкие обозначения).

---

## 9. Experiment 5 — JRC-Names и альтернативные ресурсы

### JRC-Names — **доступен и работает** (проверено)

- Файл: `https://wt-public.emm4u.eu/data/entities.gzip` — 14.2 MB gzip,
  ≈3.4 GB распакованный, **last-modified 2024-03-15** (одна из причин —
  «daily» апдейты больше не поддерживаются; документация молчит).
- Legacy RDF/distribution: `cidportal.jrc.ec.europa.eu` → HTTP 500 (dead),
  `data.europa.eu/sparql` — жив, но triples JRC-Names оттуда выгружены.
  Download page: `joint-research-centre.ec.europa.eu/.../jrc-names_en` →
  matcher `JRCNames.jar.zip` (451 KB) жив.
- Формат: TSV `entityID\tpersonOrOrg\tlanguageCode\tspellingsByNameUse`
  (`+` = пробел), 1.45 млн. строк.
- Типы: **только persons (92.7%) и organisations (7.3%)**. **Локаций нет.**
- Кириллических вариантов: **80 668 (5.6%)** из 1.45 млн, примеры:
  `Геннадий Борисов`, `Николай Красников`, `Андрей Нарышкин`,
  `Елена Кондратюк` (+ вин. падежные варианты).
- Функциональный тест EN→ID→RU: `Gennady Borisov→1072478→Геннадий Борисов`
  ✔; `Nikolai Krasnikov→1194758→Николай Красников` ✔; `Andrey Naryshkin→
  806677→Андрей Нарышкин` ✔; для `George Tabayan` и
  `Antonina Presnyakova` RU-вариантов **нет** (≈40% персоналий без RU).
- Лицензия: `LICENCE-EULA_JRC-Names_2011.pdf` (free-of-charge non-exclusive);
  Ничего менее, чем «free», но не data-portal-friendly.

**Вывод**: практическая пригодность для WTQ **низкая как основной ресурс**,
ограниченно как fallback персоналий; работает как дополнительный корпус spelling-вариантов. Для WIkiTableQuestions (где Location и
Sports team — большие доли) JRC-Names **не покрывает** большие классы.

### Кратко по альтернативам

| Ресурс | purpose | доступность | EN↔RU coverage | entity ID | пригодность batch |
|---|---|---|---|---|---|
| Wikidata API | resolve+labels | живой, rate-limited | 56% RU-форм | QID | да (кэш) |
| Wikipedia API | fallback + langlinks | живой | 43.6% | да | да |
| JRC-Names | персоналии fallback | живой (1 URL) | 5.6% кириллицы | числовой ID | ограниченно (3.4 GB) |
| DBpedia | url/uri | не проверено в глубину | ему место как label — редкая потребность | dbr: | да, но RU label реже WD |
| перевод-корпуса/TM | готовые EI↔RU пары | вне фокуса: WTQ Domain (с sport/history) не покрывается | — | — | — |

---

## 10. Experiment 6 — Сравнение QC-метрик

`results/exp6_qc.jsonl`, `exp6_qc_stats.json`; n=200, reverse-lookup на
60 формы (subsampled).

| Метрика | Результат | Комментарий |
|---|---|---|
| **A. Round-trip exact** | 6/112 (5.4%) RU форм проходят | ненадёжна: **правильные переводы падают** |
| **B. Normalized lexical match** EN label ↔ source | 57.7% linked | метрика «сущность совпадает по поверхности» только; 42% — легальные aliases/перефразы |
| **C. Entity identity** (reverse QID == forward QID) | 39/112 (34.8%) verified; 67 unresolved; 6 mismatch | лучший блокирующий сигнал из проверенных |
| **D. TM restoration / consistency** | 0 конфликтов RU на одинаковые значения (190 уникальных surface из 200) | дедупликация valuable: 190 ≠ 200 ⇒ TM реально экономит 5% |
| **E. LLM judge** | **NOT RUN** — нет ключей | — |

**Round-trip ошибается в обе стороны** (обязательный кейс):
- `Yinchuan → Иньчуань` round-trip exact fails, но перевод правильный;
- `current → течение` (в колонке «Deleted») round-trip passes, но реальное
  прочтение «до настоящего времени» ⇒ перевод неверный.

Разделение по «identity»:
- `entity_linked` 195/200;
- `entity_identity_verified` 34.8% (в среднем);
- `entity_identity_unresolved` 67/112 RU-форм — преимущественно из-за
  неполного RU-индекса (то есть из-за отсутствия обратной ссылки, а не из-за
  ошибки перевода).

---

## 11. Успешные и неуспешные примеры

12+ кейсов с подтверждения (`samples/case_studies.json`). Ключевые (кратко):

| Кейс | Что показал |
|---|---|
| `National Football League Round 6` (Cork, Dublin в строке) | WD top-1 = американский NFL ⇒ **nullбез строки решения** |
| `Red Box` | значение без header неоднозначно (band/box) |
| `@ Giants` | вопрос не помогает, строка помогает; `@`-маркер важен |
| `BMW Motorsport GmbH → BMW M` | подмена («ковой» наименование) |
| `Toronto Maple Leafs → Торонто Мейпл Лифс` | верная RU форма, round-trip exact fails |
| `current → течение` | round-trip проходит, перевод неверный |
| `Allsvenskan → Чемпионат Швеции по футболу` | «описывающая» RU форма вместо имени |
| `Cooper-Maserati → Купер (команда Формулы-1)` | RU label с служебной скобкой — нужно stripping |
| `Ha-218` | подводный класс vehículo wrongly linked |
| `[Data unknown/missing. You can help!]` | шаблонный мусор — не entity |
| `DIGIT FIVE / U+0059` | юникодные junk ответы |
| `Smith/Smyth` | коллизия транслитерации — только entity ID различает |
| `New York / London / George` | традиционные формы недоступны из правил |
| `Yinchuan → Иньчуань` | валидное RU из sitelink |
| `Der bleiche Zauberer` | источник не на английском; WD пусто; транслитерация fallback |

---

## 12. Сравнение источников (коротко)

- **RU-форма ширее всего у ru label** (+28 pp vs sitelink), но она «дескриптивна».
- **ru sitelink** — единственный источник с «естественным» названием
 (54/195 cyrillic), но + 47% latency (два запроса вместо одного) не даёт
 покрытия.
- **aliases** — практически не добавляет (41 cyrillic vs 86 у label;
 overlap почти полный).
- **JRC-Names** — только persons × ~40% и organisations × ~5% coverage
 (по нашему probe: 3/5 персоналий имели RU).

---

## 13. Сравнение QC-метрик (акцент на decision)

`results/exp6b_status.jsonl`, 200 ячеек:

```
VERIFIED 33 · ACCEPTABLE_WITHOUT_ENTITY_ID 14 · AMBIGUOUS 66
SUSPICIOUS 36 · UNRESOLVED 36 · NA_ENTITY_QC 15
```

Сверка с ручной разметкой 40 примеров (single-rater):
- согласование rule-status: **30/40 strictly**, 4/40 partial, 6/40 «wrong»;
- **harmful suggestion rate** среди «принятых» статусов по gold ≈ **20%**
  (3 из 14 VERIFIED/ACCEPTABLE) — верхняя оценка без LLM re-check;
- примеры «rule miss»: `Toronto Maple Leafs` и `Олимпийские игры` корректно
  разрешены, но попали в AMBIGUOUS (чустро строгое runner-up правило).

**Рекомендации по блокирующим QC:**
1. **блокировать** результат нельзя если `identity_verified=False` AND
   `(ambiguous OR suspicious)` AND нет LLM-judge подтверждения;
2. **round-trip exact НЕ должен быть блокирующим** (только диагностика);
3. normalized-lex match НЕ блокирует (много легитимных расхождений);
4. на false positives/immutable (`N/A`, `current`, `[Data unknown...]`,
   `DIGIT FIVE`) entity QC не применяется — им нужен отдельный
   semantic/translation validation.

---

## 14. Ограничения (коротко)

см. `environment.md`: no LLM ⇒ Experiments 1/6E и «генерация русской формы»
не покрыты; малые страты; single-rater gold; reverse subsample; non-Latin
скрипты вне выборки; wall-clock latency, но не честный per-item timing.

---

## 15. Рекомендуемая архитектура (v1, без LLM обязательств)

1. **Классификация ячеек** — CoreNLP-подобный тегер (уже есть в
   `training.tagged`) + правил по колонке-header:
   `entity_containing`, `immutable`, `template_junk`, `non_latin`, `latin_ok`.
2. **Translation memory доминирует**: уникальный (`source normalized`) →
   `(ru_form, qid?, flags)`; дедуп 190/200 ⇒ экономия ~5–15% запросов
   dataset-wide (теоретическую до 40% на повторяющихся tables).
3. **Wikidata resolver** (batch, кэш):
   wbsearchentities → WP search fallback → ранжирование (sim + P31 from
   header + disambig-penalty) → RU form `sitelink > label > alias` →
   хранить `qid`, `ru_form`, flags.
4. **Fallback-цепочка**:بد RU → традиционный словарь (.TRUE.),
   потом транслитерация с флагом `transliteration_collision`;
   иначе — маркер «RU form missing» для ручной проверки.
5. **Сохранение** в output: `ru_text`, `qid`, `ru_source`,
   `flags[]`, **`original_english`** — поверх таблицы в metadata
   (сохранение identity как в wtq-translator уже сделано через columns/
   coordinates).
6. **QC decision rule** (как в протоколе 19): ACCEPT только при
   `identity_verified` OR `(clean RU + high-confidence string match)`
   OR LLM-judge; REVIEW — `AMBIGUOUS/SUSPICIOUS/UNRESOLVED`;
   REJECT — «substitution/meaning change» (нужен LLM judge или человек).

**Кого отправлять на ручную проверку**: при текущих эвристиках 51%,
по нашим gold-оценкам фактически нужно **~25%** (после Islands
проверки 40 примеров) — a proceeds: первый concern — reduce exact through
LLM judge, второй — человек.

---

## 16. Следующие эксперименты

1. Experiment 1 (контекстные режимы A–D) — нужен LLM endpoint.
2. Расширить identity через SPARQL batch (один запрос на все RU-формы)
   вместо 60-sample reverse-lookup.
3. LLM-judge full sweep (Experiment 6/E) — вернуть те же 40 gold, чтобы
   измерить подписываем за auto-verdict при judge.
4. Написать отдельный «традиционный словарь» EN→RU (first names + фамилии +
   география) 1–2 К(!) entries из ruwiki titles — измерить покрытие.
5. Учитывать non-Latin sources (иврит/квир) — отдельный miniscript.
6. Проверить DBpedia и уникальные head-labels в качестве cross-source
   agreement метрика (quick win?).

---

## 17. Что может понадобиться в wtq-translator (только описание — не реализация)

1. В менеджер уникальных значений добавить классurile `entity_cell` с полями
   `qid`, `ru_source`, `flags` и их копирование существует уже координатно —
   понадобится tolerance для `_repeated_cells` repeat counts.
2. Входные данные `tagged/*-tagged/*.tagged` (по-страничные) могут служить
   источником entity-списков без LLM-скана.
3. QC quality report — взять ключевые поля `flags`, `identity`, `status`.
4. Слой `resolvers` (externally новый модуль) с cache_schema `qid→ru`, чтобы
   reuse смотрело и transслитерацию fallback.
5. Для `shell_only`/`mentions_only` режимов это исследование позволяет
   замить «entity-тяжелые» ячейки как «needs review», а не переводить их
   generic-LLM.

---

## 18. Ответы на обязательные вопросы (25)

1. **Стоит ли использовать Wikidata?** — Да, стоит (но не как onyone-
   останов). (сек. 6)
2. **Для чего?** — entity resolution (QID) + validation; для перевода —
   кандидат RU-форма, но не сама по себе («RU form missing» 44%).
3. **Aliases полезны?** — Практически нет: +0 новых RU-форм, только 4/200;
  полезность как tie-breaker снизу (alias 41 cyrillic).
4. **JRC-Names?** — Доступен, но только persons/orgs, RU-варианты 5.6%;
   как fallback персоналий; не как основной.
5. **Транслитерация достаточна для?** — для одиночных персоналий и
   геонames с традиционным словарём; НЕ для организаций/команд (сек. 8).
6. **Мин. контекст для переводчика?** — value + header + row (столбец
   и строка); обе обязательные по кейсам `@ Giants`, `NFL Round 6`; вопрос
   и page-title добавляют, но не заменяют.
7. **Entity ID для всех ячеек?** — Нет — только для entity-containing
   (~92% нашей выборки); остальным (FP 7.5%, immutable) нужен семантический
   контроль без ID.
8. **Хранение пары** — TM key-value: `norm(source) → (ru, qid, flags)`;
   оригинальный EN сохранить в `original_english` per-cell metadata (как
   сделано wtq-translator) — foundation для identity-preservation тестов.
9. **QC-блокирующие метрики**: `identity_verified` + (lack of
   harmful-substitution), `material error` от judge (не LLM при run now) —
   блокируют; **round-trip exact — только диагностика**.
10. **Только диагностика**: round-trip exact EN↔RU, normalized lexical
    EN label=source match, «RU form is Latin» (как warning).
11. **Доля ручной проверки**: по правилам v1 ≈51%; целевая после улучшения
    candidate ranking (учёт P31 by header), по rough-оценке 20–25%.
    Точная доля для уточнения в п. 16.
12. **Мин. pipeline**: см. секцию 15 (7 шагов: make class → TM →
    WD resolver → fallback chain → хранение → QC → review).

---

## 19. Критерии успеха

- [x] WikiTableQuestions не изменён (git status clean)
- [x] wtq-translator не изменён (pre-existing untracked `.idea/` — не от нас)
- [x] 200-example стратифицированная выборка, seed=42, dev/eval разделение
- [x] существующая NER использована; свой NER не запускался
- [x] CSV↔page JSON сопоставление через N/M (и table-metadata.tsv captions)
- [x] copy baseline; контекстные режимы — отложены (LLM недоступен,
      зафиксировано препятствие, ничего не имитировалось)
- [x] Wikidata/Wikipedia как источники кандидатов (не как GT)
- [x] JRC-Names проверен фактически (файл + функциональные пробы)
- [x] QC-метрики сравнены, показаны errors round-trip в обе стороны
- [x] entity identity проверена отдельно
- [x] архитектура рекомендована
- [x] никаких изменений в wtq-translator
