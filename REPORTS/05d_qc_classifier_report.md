# REPORT — Эксперимент 5D: обученный QC-классификатор vs LLM-judge vs rules

## Постановка

Лёгкий классификатор (logistic regression / gradient boosting, без нейросети)
на табличных фичах из УЖЕ собранных артефактов; целевая переменная — manual
needs_review из `gold_llm_translations_40.json` (40 reused cases, single-rater).
n=40 — **proof-of-concept**, не production-ready (риск переобучения).

## Фичи (из существующих артефактов, не пересчитывались)

identity_verified · reverse_mismatch · resolver_score · lex_match_en ·
ru_cyrillic · ru_source_sitelink · header_keyword_team/country · pn_match ·
pn_type_matches · dict_agreement_max · llm_confidence (+sq) ·
status_flag_ambiguous · is_entity_stratum. Target: needs_review (22/40
positive). CV: **leave-one-out** (n=40).

## Результаты (LOO)

| Модель | agreement | F1 | pred review rate |
|---|---:|---:|---:|
| LogisticRegression | 0.55 | 0.625 | 0.65 |
| **GradientBoosting** | **0.65** | **0.682** | **0.55** |
| rule-based (SUSPICIOUS/AMBIGUOUS → review) | 0.55 | — | 0.40 |
| LLM-judge qwen3b (needs_review) | 0.55 | — | 0.85 |

- GradientBoosting даёт **65% против 55%** у rule-based и judge —
  но при n=40 и LOO разница НЕ статистически значима (CI ~±15 пп).
- Top признаки (logreg coef): `pn_match (+1.24)`, `is_entity_stratum (+0.97)`,
  `status_flag_ambiguous (+0.68)`, `ru_source_sitelink (−0.44)`,
  `header_keyword_team (+0.44)`, `lex_match_en (−0.43)`.

## Интерпретация

- Классификатор «предсказывает» review через proxy-фичи (stratum, ambiguous
  flag, PN match), т.е. фактически воспроизводит rule-based логику —
  независимой доп-информации мало.
- LLM self-confidence (llm_confidence) почти не помогает (coefs +0.05/+0.09):
  self-reported confidence не калиброван (подтверждение этапа 2).
- Для валидного вывода нужно ≥ несколько сотен размеченных примеров
  (детерминированная разметка 40 → нужно расширить human gold или
  проксировать шумность через judge-конфликт).

## Ограничения

1. n=40 — переобучение неизбежно; leave-one-out смещён optimistic.
2. Фичи предназначены для entity-контекста; false-positive строки
   (NA_ENTITY_QC) в классификаторе грубо учтены через is_entity_stratum.
3. Не стоит публиковать как QC-модель; это доказательство концепции
   «фичи дешевле LLM-judge».

Результат: `results/qc_classifier_results.json`.
