# Data Dictionary

Every table in `data/processed/drug_safety.duckdb`, what one row means (the **grain**), and what each column holds.

**How to use this:** learn the ★ tables well enough to explain them without notes. For the rest, knowing what they are for is enough.

| Priority | Tables |
|---|---|
| ★ Know well | `stg_sider_se`, `int_map_candidates`, `xwalk_stitch_drugbank`, `dim_drug`, `dim_side_effect`, `bridge_drug_atc`, `fact_drug_side_effect`, `an_class_signals` |
| Know the purpose | everything else |

---

## Glossary: the IDs and terms you'll see

| Term | What it is | Example |
|---|---|---|
| **STITCH ID** | SIDER's compound ID. `CID1` + 8 digits = "flat" (stereochemistry ignored); `CID0` + 8 digits = "stereo" (one specific 3D form). The digits are a PubChem ID. | `CID100047725` → PubChem `47725` |
| **PubChem CID** | Compound ID from the NIH PubChem database. The bridge between SIDER and DrugBank. | `47725` |
| **DrugBank ID** | DrugBank's drug ID. The main drug key in this project. | `DB01076` (atorvastatin) |
| **UMLS CUI** | Concept ID from the US National Library of Medicine's vocabulary. Used here as the ID for side effects and conditions. | `C0035410` |
| **MedDRA** | The standard medical vocabulary regulators use for side effects. Two levels appear here: | |
| — **LLT** (Lowest Level Term) | The exact wording on the label | "Abdominal cramps" |
| — **PT** (Preferred Term) | The standard grouping several LLTs roll up to | "Abdominal pain" |
| **ATC code** | WHO drug-class code with 5 levels; each level adds characters. | `C10AA05` (atorvastatin) |
| — Level 1 | Anatomical group (1 letter) | `C` cardiovascular system |
| — Level 2 | Therapeutic group (3 characters) | `C10` lipid modifying agents |
| — Level 3 | Pharmacological group (4) | `C10A` lipid modifying agents, plain |
| — Level 4 | Chemical group (5) | `C10AA` HMG CoA reductase inhibitors (statins) |
| — Level 5 | The single substance (7) | `C10AA05` atorvastatin |
| **Indication** | A condition the drug is approved to treat | Hypertension |
| **Placebo arm** | The group in a clinical trial given a dummy pill; its side-effect rate is the baseline | |
| **Post-marketing** | Reported after the drug went on sale, not in the original trials | |

---

## How the tables connect

```
stg_* (raw)  →  int_sider_compounds → int_map_candidates → xwalk_stitch_drugbank  (the merge)
                                                                   │
dim_drug ─┬─ bridge_drug_atc ── dim_atc_class                      │ every fact joins through
          ├─ fact_drug_side_effect ── dim_side_effect   ◄──────────┘ drugbank_id
          └─ fact_drug_indication  ── dim_condition
                     │
                     ▼
              an_* (results)
```

**Join keys:** `drugbank_id` (drugs), `side_effect_id` (side effects), `condition_id` (conditions), `l1`–`l4` / `atc_class` (drug classes), `stitch_flat` (raw SIDER → crosswalk).

---

## 1. Raw staging tables (`stg_`)

Loaded from the files in `data/raw/` with no business logic. Types are set explicitly so nothing is guessed.

### ★ `stg_sider_se` — 309,849 rows
**Grain:** one row per compound × label term × MedDRA level. Each label term usually appears **twice**: once as LLT, once as its PT.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `stitch_flat` | VARCHAR | Compound ID, stereo-free | `CID100000085` |
| `stitch_stereo` | VARCHAR | Compound ID, stereo-specific | `CID000010917` |
| `umls_cui_label` | VARCHAR | ID of the term exactly as found on the label | `C0000729` |
| `meddra_type` | VARCHAR | `LLT`, `PT`, or blank (901 rows) | `LLT` |
| `umls_cui_meddra` | VARCHAR | ID of the MedDRA term this row represents. **Becomes `side_effect_id`.** | `C0000729` |
| `side_effect_name` | VARCHAR | Name of that MedDRA term | `Abdominal cramps` |

### `stg_sider_freq` — 291,632 rows
**Grain:** one frequency statement on a label. A drug–side-effect pair can have many (several trials, drug vs placebo arm, LLT and PT).

| Column | Type | Meaning | Example |
|---|---|---|---|
| `stitch_flat`, `stitch_stereo` | VARCHAR | As above | |
| `umls_cui_label` | VARCHAR | Term as found on the label | `C0000737` |
| `placebo` | VARCHAR | `placebo` if this is the placebo arm, else empty | NULL |
| `freq_description` | VARCHAR | Raw text: a percentage, a range, a word band, or "postmarketing" | `21%`, `common`, `postmarketing` |
| `freq_lower` | DOUBLE | Lower bound as a proportion (0–1) | `0.21` |
| `freq_upper` | DOUBLE | Upper bound as a proportion. Equal to `freq_lower` when exact; `common` = 0.01–1.0 | `0.21` |
| `meddra_type`, `umls_cui_meddra`, `side_effect_name` | VARCHAR | As in `stg_sider_se` | |

### `stg_sider_indications` — 30,835 rows
**Grain:** one condition mention on a label × MedDRA level.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `stitch_flat` | VARCHAR | Compound ID | |
| `umls_cui_label` | VARCHAR | Condition as found on the label | |
| `detection_method` | VARCHAR | `NLP_indication` (what it treats — the only one used), `NLP_precondition` (closer to a contraindication), `text_mention` (named anywhere, including warnings) | `text_mention` |
| `concept_name` | VARCHAR | Label wording | `Failure to Thrive` |
| `meddra_type` | VARCHAR | `LLT` / `PT` | |
| `umls_cui_meddra` | VARCHAR | MedDRA term ID. **Becomes `condition_id`.** | |
| `meddra_name` | VARCHAR | MedDRA term name | `Failure to thrive` |

### `stg_drugbank` — 7,759 rows
**Grain:** one DrugBank drug.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `drugbank_id` | VARCHAR | Drug ID | `DB00001` |
| `name` | VARCHAR | Drug name | `Lepirudin` |
| `type` | VARCHAR | `small molecule` or `biotech` | `biotech` |
| `groups` | VARCHAR | Approval statuses, `\|`-separated | `approved\|withdrawn` |
| `atc_codes` | VARCHAR | ATC level-5 codes, `\|`-separated, from ~2016 | `B01AE02` |
| `categories` | VARCHAR | DrugBank's own categories, `\|`-separated (not used) | `Antithrombins\|...` |

### `stg_map_inchi` (6,300) · `stg_map_unichem` (204,709) · `stg_map_curated` (1,283)
The three ways to link a SIDER compound to DrugBank. **Grain:** one candidate link.

| Table | Columns | How the link was made |
|---|---|---|
| `stg_map_inchi` | `drugbank_id`, `pubchem_cid` | Exact chemical-structure (InChI) match. Most precise. |
| `stg_map_unichem` | `drugbank_id`, `pubchem_cid` | Same atom connectivity. Broad: one drug maps to many PubChem IDs (salts, mixtures). |
| `stg_map_curated` | `stitch_flat`, `drugbank_id` | Hand-checked SIDER → DrugBank crosswalk by D. Himmelstein. |

### `stg_atc_2026` (6,996) · `stg_atc_2021` (6,440)
**Grain:** one ATC code at any level. Columns: `atc_code`, `atc_name`. The 2021 file finds names for codes WHO has since retired.

---

## 2. The merge (`int_`, `xwalk_`, `qa_`, `ref_`)

### `int_sider_compounds` — 2,993 rows
**Grain:** one distinct (flat, stereo) pair seen in any SIDER file. Indication-only compounds have no stereo ID.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `stitch_flat`, `stitch_stereo` | VARCHAR | STITCH IDs | `CID100000158`, `CID005280360` |
| `pubchem_flat`, `pubchem_stereo` | BIGINT | The PubChem IDs decoded from them | `158`, `5280360` |

### ★ `int_map_candidates` — 3,526 rows
**Grain:** one possible (compound → drug) link from one source. **A compound can have several rows**: this is the many-to-many problem.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `stitch_flat` | VARCHAR | SIDER compound | `CID100003405` |
| `drugbank_id` | VARCHAR | A candidate drug | `DB00158` |
| `source_rank` | INTEGER | 1 = InChI, 2 = curated, 3 = UniChem (lower wins) | `2` |
| `map_source` | VARCHAR | Name of the source | `curated_crosswalk` |

### ★ `xwalk_stitch_drugbank` — 1,137 rows
**Grain:** exactly one row per mapped SIDER compound (checked by a data-quality assertion). Several compounds can map to the same drug (racemate and enantiomer): 41 drugs have more than one.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `stitch_flat` | VARCHAR | SIDER compound (unique) | `CID100000214` |
| `drugbank_id` | VARCHAR | The one chosen drug | `DB00770` |
| `map_source` | VARCHAR | Which source won | `inchi_exact` |
| `n_candidates_same_rank` | BIGINT | How many candidates tied at that source before the tie-break (1 = no tie) | `1` |

### `qa_mapping_summary` — 4 rows
Compounds per winning source, plus `UNMAPPED`. Columns: `map_source`, `sider_compounds`. Counts compounds from all SIDER files, including indication-only ones.

### `ref_serious_pts` — 61 rows
The author-curated list of serious MedDRA preferred terms (in `src/config.py`). Column: `pt_name`. Three names on the list don't occur in SIDER's older MedDRA version, so 58 match.

---

## 3. The star schema — the tables you analyse

### ★ `dim_drug` — 1,074 rows
**Grain:** one DrugBank drug that has at least one side effect.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `drugbank_id` | VARCHAR | **Primary key** | `DB00014` |
| `drug_name` | VARCHAR | Name | `Goserelin` |
| `drug_type` | VARCHAR | `small molecule` / `biotech` | |
| `approval_groups` | VARCHAR | e.g. `approved`, `investigational`, `withdrawn` | `approved` |
| `n_side_effects` | BIGINT | Distinct side effects (PT) on its label | `229` |
| `n_serious_side_effects` | BIGINT | Of those, how many are on the serious list | `12` |
| `n_indications` | BIGINT | Distinct labelled conditions | `4` |
| `primary_atc_l1` | VARCHAR | Most common level-1 class (NULL for 125 drugs with no ATC code) | `L` |
| `atc_l4_codes` | VARCHAR | All its level-4 classes, `\|`-separated | `L02AE` |

### ★ `dim_side_effect` — 4,048 rows
**Grain:** one MedDRA preferred term that appears on at least one mapped drug.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `side_effect_id` | VARCHAR | **Primary key** (UMLS CUI) | `C0003811` |
| `side_effect_name` | VARCHAR | Name (British MedDRA spelling: *haemorrhage*, *oedema*) | `Arrhythmia` |
| `is_serious` | BOOLEAN | On the serious list | `false` |
| `n_drugs` | BIGINT | How many drugs list it | `350` |

### `dim_condition` — 1,116 rows
**Grain:** one condition (PT) at least one mapped drug is labelled for. Columns: `condition_id` (primary key), `condition_name`, `n_drugs`.

### `dim_atc_class` — 734 rows
**Grain:** one class at one level (1–4). Columns: `level`, `atc_class` (the code), `class_name`.

### ★ `bridge_drug_atc` — 1,394 rows
**Grain:** one drug × one ATC level-5 code. A **bridge table** because a drug can belong to several classes (949 drugs, 1,394 links).

| Column | Type | Meaning | Example |
|---|---|---|---|
| `drugbank_id` | VARCHAR | Drug | `DB01378` |
| `atc_code` | VARCHAR | Full 7-character code from DrugBank | `A02AA01` |
| `code_status` | VARCHAR | `current_2026` (1,351), `retired_found_in_2021` (6), `not_found` (37) | `current_2026` |
| `l1`, `l1_name` | VARCHAR | Level 1 code and name | `A`, ALIMENTARY TRACT AND METABOLISM |
| `l2`, `l2_name` | VARCHAR | Level 2 | `A02`, DRUGS FOR ACID RELATED DISORDERS |
| `l3`, `l3_name` | VARCHAR | Level 3 | `A02A`, ANTACIDS |
| `l4`, `l4_name` | VARCHAR | Level 4 | `A02AA`, Magnesium compounds |

### ★ `fact_drug_side_effect` — 121,247 rows
**Grain:** one drug × one side effect (PT) on its label. **Composite key:** (`drugbank_id`, `side_effect_id`), unique (checked). This is the main table.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `drugbank_id` | VARCHAR | → `dim_drug` | `DB00583` |
| `side_effect_id` | VARCHAR | → `dim_side_effect` | `C0687713` |
| `freq_drug` | DOUBLE | Median rate in the drug arm, 0–1. Only precise frequencies (range ≤ 5 points). NULL for 59% of rows. | `0.075` = 7.5% |
| `freq_placebo` | DOUBLE | Median rate in the placebo arm, same rule | `0.17` |
| `excess_over_placebo` | DOUBLE | `freq_drug − freq_placebo`, only when both exist (10,379 rows). Negative = more common on placebo. | `-0.095` |
| `reported_postmarketing` | BOOLEAN | At least one frequency row says "postmarketing" | `false` |
| `postmarketing_only` | BOOLEAN | Every drug-arm frequency row is "postmarketing", i.e. never seen in the trials reported on the label. FALSE when there are no frequency rows. | `true` |

### `fact_drug_indication` — 4,017 rows
**Grain:** one drug × one condition it treats (`NLP_indication` only). Columns: `drugbank_id`, `condition_id`.

---

## 4. Analysis results (`an_`)

### ★ `an_class_signals` — 42,665 rows
**Grain:** one tested (drug class × side effect) pair. Classes at ATC levels 2–4 with ≥ 4 drugs; side effects on ≥ 3 drugs in the class. The universe is the 949 drugs with an ATC class.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `level` | INTEGER | ATC level of the class (2, 3, 4) | `2` |
| `atc_class`, `class_name` | VARCHAR | The class | `J01`, ANTIBACTERIALS FOR SYSTEMIC USE |
| `side_effect_id`, `side_effect_name`, `is_serious` | | The side effect | Pseudomembranous colitis |
| `drugs_in_class` | BIGINT | Class size (a + b) | `74` |
| `drugs_in_class_with_se` | BIGINT | Drugs in the class listing it (a) | `48` |
| `pct_in_class` | FLOAT | a ÷ (a + b) | `0.649` |
| `pct_outside_class` | FLOAT | c ÷ (c + d): share of all other classified drugs | `0.009` |
| `odds_ratio` | FLOAT | (a·d) ÷ (b·c) with +0.5 added to each cell | `186.8` |
| `or_ci_low`, `or_ci_high` | FLOAT | 95% confidence interval of the odds ratio | `81.9`–`426.2` |
| `lift` | FLOAT | `pct_in_class ÷ pct_outside_class` | `70.9` |
| `p_value` | DOUBLE | One-sided Fisher's exact test | `3.8e-53` |
| `q_value` | DOUBLE | Benjamini–Hochberg adjusted p-value (false discovery rate) | `1.6e-48` |
| `is_signal` | BOOLEAN | `q_value < 0.05 AND odds_ratio >= 2` (13,667 rows) | `true` |

### `an_known_effect_check` — 18 rows
The validation. **Grain:** one textbook class effect listed in `src/config.py` before looking at results. Columns: `atc_class`, `class_label`, `side_effect_name`, `status` (`recovered` / `not significant` / `not tested (too few drugs)`), `odds_ratio`, `q_value`, `pct_in_class`, `pct_outside_class`.

### `an_drug_neighbours` — 5,370 rows
**Grain:** one drug × one of its 5 most similar drugs. Columns: `drugbank_id`, `rank` (1 = most similar), `similar_drugbank_id`, `jaccard` (shared side effects ÷ side effects in either, 0–1).

### Views `an_q01` … `an_q09` (from `sql/04_analysis_queries.sql`)

| View | Rows | One row per | Key columns |
|---|---|---|---|
| `an_q01_data_funnel` | 5 | merge step | `step`, `stage`, `n` |
| `an_q02_top_side_effects` | 40 | side effect (top 40) | `n_drugs`, `pct_of_drugs` |
| `an_q03_burden_by_class` | 14 | ATC level-1 group | `median_side_effects`, `median_serious`, `pct_with_any_serious` |
| `an_q04_class_heatmap` | 350 | group × top-25 side effect | `pct_of_drugs` |
| `an_q05_placebo_adjusted` | 10,379 | drug × side effect with both arms | `freq_drug`, `freq_placebo`, `excess_over_placebo`, `relative_risk` |
| `an_q06_nocebo_effects` | 193 | side effect with both arms on ≥ 10 drugs | `median_excess` (sorted lowest first) |
| `an_q07_postmarketing_serious` | 53 | serious side effect on ≥ 20 labels | `share_postmarketing_only` |
| `an_q08_condition_options` | 3,011 | condition × approved drug (conditions with ≥ 3) | `n_serious_side_effects`, `burden_rank` |
| `an_q09_label_length_check` | 4 | band of label length | `avg_serious`, `avg_indications` |

---

## Things that trip people up

- **Proportions, not percentages.** `freq_drug = 0.075` means 7.5%. Multiply by 100 in Tableau/Power BI or format as %.
- **NULL frequency ≠ zero.** NULL means the label gave no precise rate, not that nobody had it.
- **Count drugs with `COUNT(DISTINCT drugbank_id)`** whenever you join through `bridge_drug_atc`; a drug in two classes appears twice.
- **British spelling.** Search `ILIKE '%haemorrh%'`, not "hemorrhage".
- **`stg_` tables double-count.** Always filter `meddra_type = 'PT'` before counting side effects in raw data.
