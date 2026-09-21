# Stage 6 — Candidate-Constrained Entity Selection: analysis

```text
Research question:
Можно ли снизить вредные замены сущностей, запретив LLM генерировать
русскую форму сущности и заставив её только выбирать один из заранее
найденных кандидатов (или NO_MATCH) с последующим детерминированным COPY?

Main finding:
YES на безопасности — 0 harmful substitutions на 40 human-кейсах у обоих
rerankers (против 12/40 у свободной генерации 3b и 5/40 у 7b-localizer
этапа 5), НО ценой высокой абстинентности: Qwen7B NO_MATCH 71%,
Qwen3B 84.5% (модель отказывается чаще, чем выбирает). Main bottleneck:
candidate retrieval (58% coverage) + over-cautious abstention, НЕ ranking.

Main bottleneck: retrieval + abstention (не ranking)
Does candidate-constrained selection reduce harmful substitutions? YES
Is LLM selection necessary? INCONCLUSIVE (deterministic B0 формально лучше
на silver; на human-40 LLM-отказы ловят неверных кандидатов resolver'а)
Does context help? NO для coverage (больше контекста → больше абстиненции;
cell-only даёт больше правильных picks, но часть — surface priors)
```

Уровни вывода разделены: (A) human-40, (B) silver/pseudo-gold, (C) oracle —
не смешаны.

---

## 1. Retrieval (RQ1)

| Метрика | Значение | n |
|---|---:|---:|
| candidate_coverage | **58%** (116/200) | 200 |
| surface_recall@1/3/5 | 37/37 | surface-gold 37 (circular — см. ниже) |
| identity_recall@1/3/5 | 44/50 = **88%** | identity-gold 50 |

- surface-gold построен из тех же кандидатов (WD/PN), поэтому surface recall
  100% — **trivially circular**, приводится как sanity-check построения,
  не как достижение.
- Реальный retrieval-провал: **84/200 пустых candidate set** — примеры,
  где resolver вообще не нашёл ни одной русской формы (junk/шаблоны,
  ambiguous multi-word, non-candidate-имена). Это entity-linking failure,
  а не ranking failure.

## RQ2. Rerankers на одинаковом candidate set (n=116)

| Method | Candidate Recall@5 | Selection Agreement | NO_MATCH | Harmful | Invalid | Latency |
|---|---:|---:|---:|---:|---:|---:|
| Resolver_B0 | 88% (identity, n=50) | **94.8%** (circular) | 0% | 6 (silver) | 0 | ~0 |
| Feature_reranker_B2 | 88% | 94.8% (circular) | 0% | 6 | 0 | ~0 |
| Qwen3B | 88% | 1.0 | 84.5% | **0** | 0 | 0.83 s (CPU) |
| Qwen7B | 88% | 1.0 | 70.7% | **0** | 0 | 1.3 s (GPU) |
| ORACLE_Qwen3B | 88% | 1.0 | 84.5% | 0 | 0 | 0.41 s |
| ORACLE_Qwen7B | 88% | 1.0 | 70.7% | 0 | 0 | 0.64 s |

- B0/B1/B2 ≈ идентичны: когда resolver даёт кандидатов, first-candidate
  почти всегда совпадает с silver (circularity: silver построен из тех же
  форм). Honest-вывод: silver НЕ может отличить «выбор правильного» от
  «воспроизведение источника».
- **На human-40** (вне круга): Resolver_B0 19 correct / **6 harmful**;
  Qwen7B 8 correct / **0 harmful**; Qwen3B 5 correct / 0 harmful.
- 6 harmful у Resolver_B0 — это ровно MANUAL_HARMFUL_FORMS (GAA→NFL,
  Гиганты-миф, Ha-218→кварталы, chord symbol, «течение», «14 ноября»):
  resolver top-1 неверен там, где верный кандидат отсутствует.

## Confusion matrix (human-40, метод Qwen7B)

```text
                    correct candidate exists
                     YES                  NO
SELECT          8 correct            0 false positive
NO_MATCH        9 missed candidate   9 correct abstention
```

Missed candidate 9 — из них большинство: junk-ячейки, где «существование
кандидата» формально есть (WD form есть), но форма дескриптивная/junk —
серые случаи silver.

## RQ3 — Context ablation (silver, n=116)

| Модель | A | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| Qwen7B correct | 58 | 51 | 41 | 34 | 32 |
| Qwen7B NO_MATCH | 50% | 56% | 65% | 71% | 72% |
| Qwen3B correct | 27 | 21 | 27 | 18 | — |
| Qwen3B NO_MATCH | 77% | 82% | 77% | 85% | — |

**Контекст НЕ улучшает selection agreement; он увеличивает abstention.**
Полный контекст показывает модели, что кандидат не совпадает с контекстом
→ NO_MATCH. Cell-only даёт больше picks — но это surface-priors (см.
SHUFFLED-контроль: в 6/6 парах «оба выбрали» выбор НЕ изменился при
перемешанном контексте; 8 NO_MATCH-flips) — т.е. LLM селекция
**фактически использует surface-совпадение, а не контекст**.

## RQ4 — NO_MATCH / abstention

- NO_MATCH когда правильный кандидат существует: 7b — 32 (silver) / 9 (human).
- Always-NO_MATCH давал бы harmful 0 при coverage 0 — модель на грани:
  7b находит баланс (34 correct), 3b — почти всегда abstain (98/116).

## RQ безопасность: FREE_GENERATION vs CANDIDATE_SELECTION (40 human)

| Method | n | harmful |
|---|---:|---:|
| free generation qwen3b (этап 2) | 40 | **12 (30%)** |
| free generation qwen7b (этап 5B) | 40 | **5 (13%)** |
| candidate selection qwen3b (этап 6) | 40 | **0** |
| candidate selection qwen7b (этап 6) | 40 | **0** |

Candidate-constrained selection **полностью устранил surface-hallucination**
(невозможно написать «Бронкос» — строка всегда копируется из кандидата).
Цена: coverage падает с ~25 attempted на 40 до 8 (7b).

## По стратам (mode D, human+silver, Qwen7B)

Полный файл: `tables/by_stratum.csv`. Наиболее проблемные: SHORT_AMBIGUOUS и
MULTI_WORD — там больше всего correct_abstain (модель честно отказывается),
LOCATION/PERSON — больше правильных picks.

## Bottleneck breakdown (§25)

```text
1. Retrieval:       ГЛАВНЫЙ — 42% примеров вообще без кандидатов
                    (entity linking fails на junk/ambiguous/multi-word);
                    identity recall на уже-linked 88%.
2. Candidate quality: BN candidates — дубли/варианты одного WD label,
                    синонимов-вариантов (Буффало/Баффало) мало;acceptable
                    forms список узкий (только WD form).
3. Ranking:         НЕ bottleneck для surface-gold (oracle == original;
                    B0 = rerankers). LLM не добавляет поверх B0.
4. Context:         LLM использует context для отказа, не для выбора;
                    negative-control подтверждает surface-priors.
5. Abstention:      Qwen консервативен (70-85% NO_MATCH) — безопасно,
                    но малополезно; NO_MATCH-когда-есть-кандидат 9/40.
6. Surface-form:    детерминированный COPY устранил hallucination
                    полностью (0/40 harmful).
```

## Recommended next experiment

**Не продолжать LLM reranker как генератор/ранкер — следующий bottleneck в
candidate retrieval / entity linking и в surface-form fallback:**
1. расширенный retrieval (WD aliases для всех, Wikipedia redirect/alias
   lookup, TM из уже переведённых таблиц) для 84 zero-candidate примеров;
2. surface-form fallback chain для NO_MATCH: ByT5 (5A) → TM → REVIEW;
   измерить harmful на расширении;
3. если retrieval вырастет — вернуть LLM reranking только на
   ambiguous-strata (SHORT_AMBIGUOUS/MULTI_WORD), где deterministic копия
   первого кандидата самая рискованная.
