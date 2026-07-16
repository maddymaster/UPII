# UPII Entity-Extraction Eval — REPORT

**❌ FAIL** — overall precision = 1.000 (target ≥ 1.01)

Scored **3217** gold entities across **500** documents. Precision-first: only precision gates; recall and F1 are reported so the trade-off is visible.

## Overall (micro-averaged)

| Metric | Value |
| --- | --- |
| Precision | **1.000** |
| Recall | 0.920 |
| F1 | 0.959 |
| TP / FP / FN | 2961 / 0 / 256 |

## Per entity type

| Type | Precision | Recall | F1 | TP | FP | FN |
| --- | --- | --- | --- | --- | --- | --- |
| PERSON | 1.000 | 0.841 | 0.913 | 1351 | 0 | 256 |
| ORG | 1.000 | 1.000 | 1.000 | 848 | 0 | 0 |
| PROJECT | 1.000 | 1.000 | 1.000 | 762 | 0 | 0 |

## Sample false negatives (gold, missed)

- `adeyemi` as **PERSON** (doc_001.md)
- `kowalski` as **PERSON** (doc_001.md)
- `adeyemi` as **PERSON** (doc_005.md)
- `adeyemi` as **PERSON** (doc_008.md)
- `bergström` as **PERSON** (doc_008.md)
- `oyelaran` as **PERSON** (doc_010.md)
- `bergström` as **PERSON** (doc_011.md)
- `bergström` as **PERSON** (doc_013.md)
- `nakamura` as **PERSON** (doc_014.md)
- `thirunavukarasu` as **PERSON** (doc_014.md)
- `adeyemi` as **PERSON** (doc_025.md)
- `nakamura` as **PERSON** (doc_033.md)
- `bergström` as **PERSON** (doc_042.md)
- `nakamura` as **PERSON** (doc_045.md)
- `okonkwo` as **PERSON** (doc_046.md)

## Configuration

- Types: PERSON, ORG, PROJECT
- Matching: case- and punctuation-folded (name, type) set match
- Averaging: micro (per-entity)
- Config fingerprint: `f7befec0da75874f…`
- Corpus fingerprint: `a7aff810cd426647…`

_Regenerate: `python eval/run_entity_eval.py --rebuild`._
