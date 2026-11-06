-- =============================================================================
-- 03_model.sql  —  Star schema for analysis and BI
--
--   dim_drug ─┬─ bridge_drug_atc ── dim_atc_class      (drug classes, many-to-many)
--             ├─ fact_drug_side_effect ── dim_side_effect
--             └─ fact_drug_indication  ── dim_condition
--
-- Grain decisions:
--   * Side effects are kept at MedDRA Preferred Term (PT) level. SIDER lists every
--     label term as a Lowest Level Term (LLT) *and* its PT; counting both would
--     double count synonyms ("Abdominal cramps" and "Abdominal pain").
--   * Several SIDER compounds can map to the same DrugBank drug (racemate and
--     enantiomer). Facts are rolled up to the DrugBank drug.
--   * Indications use only NLP_indication rows. "text_mention" catches any
--     condition named anywhere on the label (including warnings), and
--     "NLP_precondition" is closer to a contraindication.
-- =============================================================================

-- ---------- Side-effect facts ----------
CREATE OR REPLACE TABLE fact_drug_side_effect AS
WITH se AS (
    SELECT x.drugbank_id, s.umls_cui_meddra AS side_effect_id
    FROM stg_sider_se s
    JOIN xwalk_stitch_drugbank x USING (stitch_flat)
    WHERE s.meddra_type = 'PT'
    GROUP BY 1, 2
),
freq AS (   -- one frequency per drug x PT x arm: median of the label's precise values
    -- Only precise frequencies (range <= 5 points, e.g. "21%" or "3-6%") are used.
    -- Word bands like "common" mean 1-100%; their midpoint (50.5%) would invent
    -- rates that were never measured.
    SELECT x.drugbank_id,
           f.umls_cui_meddra AS side_effect_id,
           MEDIAN(CASE WHEN f.placebo IS NULL AND f.freq_upper - f.freq_lower <= 0.05
                       THEN (f.freq_lower + f.freq_upper) / 2 END)                     AS freq_drug,
           MEDIAN(CASE WHEN f.placebo = 'placebo' AND f.freq_upper - f.freq_lower <= 0.05
                       THEN (f.freq_lower + f.freq_upper) / 2 END)                     AS freq_placebo,
           BOOL_OR(f.freq_description = 'postmarketing')                                     AS reported_postmarketing,
           BOOL_AND(f.freq_description = 'postmarketing' OR f.placebo = 'placebo')           AS postmarketing_only
    FROM stg_sider_freq f
    JOIN xwalk_stitch_drugbank x USING (stitch_flat)
    WHERE f.meddra_type = 'PT'
    GROUP BY 1, 2
)
SELECT se.drugbank_id,
       se.side_effect_id,
       freq.freq_drug,
       freq.freq_placebo,
       CASE WHEN freq.freq_drug IS NOT NULL AND freq.freq_placebo IS NOT NULL
            THEN freq.freq_drug - freq.freq_placebo END AS excess_over_placebo,
       COALESCE(freq.reported_postmarketing, FALSE)     AS reported_postmarketing,
       COALESCE(freq.postmarketing_only, FALSE)         AS postmarketing_only
FROM se
LEFT JOIN freq USING (drugbank_id, side_effect_id);

-- ---------- Side-effect dimension ----------
CREATE OR REPLACE TABLE dim_side_effect AS
SELECT s.umls_cui_meddra AS side_effect_id,
       MODE(s.side_effect_name) AS side_effect_name,      -- a few CUIs carry >1 spelling
       MODE(s.side_effect_name) IN (SELECT pt_name FROM ref_serious_pts) AS is_serious,
       (SELECT COUNT(*) FROM fact_drug_side_effect f WHERE f.side_effect_id = s.umls_cui_meddra) AS n_drugs
FROM stg_sider_se s
WHERE s.meddra_type = 'PT'
  AND s.umls_cui_meddra IN (SELECT side_effect_id FROM fact_drug_side_effect)
GROUP BY 1;

-- ---------- Condition (indication) facts and dimension ----------
CREATE OR REPLACE TABLE fact_drug_indication AS
SELECT DISTINCT x.drugbank_id, i.umls_cui_meddra AS condition_id
FROM stg_sider_indications i
JOIN xwalk_stitch_drugbank x USING (stitch_flat)
WHERE i.meddra_type = 'PT' AND i.detection_method = 'NLP_indication';

CREATE OR REPLACE TABLE dim_condition AS
SELECT i.umls_cui_meddra AS condition_id,
       MODE(i.meddra_name) AS condition_name,
       COUNT(DISTINCT x.drugbank_id) AS n_drugs
FROM stg_sider_indications i
JOIN xwalk_stitch_drugbank x USING (stitch_flat)
WHERE i.meddra_type = 'PT' AND i.detection_method = 'NLP_indication'
GROUP BY 1;

-- ---------- Drug classes (WHO ATC) ----------
-- DrugBank's ATC codes date from ~2016; WHO has since retired some (e.g. the
-- 2022 restructure of L01 cancer drugs). Resolve each code against the 2026
-- release, fall back to the 2021 release, and flag what happened.
CREATE OR REPLACE TABLE bridge_drug_atc AS
WITH codes AS (
    SELECT DISTINCT d.drugbank_id, TRIM(UNNEST(string_split(d.atc_codes, '|'))) AS atc_code
    FROM stg_drugbank d
    WHERE d.atc_codes IS NOT NULL
      AND d.drugbank_id IN (SELECT drugbank_id FROM xwalk_stitch_drugbank)
),
lvl AS (
    SELECT drugbank_id, atc_code,
           substr(atc_code, 1, 1) AS l1, substr(atc_code, 1, 3) AS l2,
           substr(atc_code, 1, 4) AS l3, substr(atc_code, 1, 5) AS l4
    FROM codes
)
SELECT l.drugbank_id, l.atc_code,
       CASE WHEN n26.atc_code IS NOT NULL THEN 'current_2026'
            WHEN n21.atc_code IS NOT NULL THEN 'retired_found_in_2021'
            ELSE 'not_found' END AS code_status,
       l.l1, COALESCE(a1.atc_name, b1.atc_name) AS l1_name,
       l.l2, COALESCE(a2.atc_name, b2.atc_name) AS l2_name,
       l.l3, COALESCE(a3.atc_name, b3.atc_name) AS l3_name,
       l.l4, COALESCE(a4.atc_name, b4.atc_name) AS l4_name
FROM lvl l
LEFT JOIN stg_atc_2026 n26 ON n26.atc_code = l.atc_code
LEFT JOIN stg_atc_2021 n21 ON n21.atc_code = l.atc_code
LEFT JOIN stg_atc_2026 a1 ON a1.atc_code = l.l1  LEFT JOIN stg_atc_2021 b1 ON b1.atc_code = l.l1
LEFT JOIN stg_atc_2026 a2 ON a2.atc_code = l.l2  LEFT JOIN stg_atc_2021 b2 ON b2.atc_code = l.l2
LEFT JOIN stg_atc_2026 a3 ON a3.atc_code = l.l3  LEFT JOIN stg_atc_2021 b3 ON b3.atc_code = l.l3
LEFT JOIN stg_atc_2026 a4 ON a4.atc_code = l.l4  LEFT JOIN stg_atc_2021 b4 ON b4.atc_code = l.l4;

CREATE OR REPLACE TABLE dim_atc_class AS
SELECT DISTINCT 1 AS level, l1 AS atc_class, l1_name AS class_name FROM bridge_drug_atc
UNION SELECT DISTINCT 2, l2, l2_name FROM bridge_drug_atc
UNION SELECT DISTINCT 3, l3, l3_name FROM bridge_drug_atc
UNION SELECT DISTINCT 4, l4, l4_name FROM bridge_drug_atc;

-- ---------- Drug dimension ----------
CREATE OR REPLACE TABLE dim_drug AS
SELECT d.drugbank_id,
       d.name AS drug_name,
       d.type AS drug_type,
       d.groups AS approval_groups,
       (SELECT COUNT(*) FROM fact_drug_side_effect f WHERE f.drugbank_id = d.drugbank_id) AS n_side_effects,
       (SELECT COUNT(*) FROM fact_drug_side_effect f JOIN dim_side_effect s USING (side_effect_id)
         WHERE f.drugbank_id = d.drugbank_id AND s.is_serious) AS n_serious_side_effects,
       (SELECT COUNT(*) FROM fact_drug_indication i WHERE i.drugbank_id = d.drugbank_id) AS n_indications,
       (SELECT MODE(b.l1) FROM bridge_drug_atc b WHERE b.drugbank_id = d.drugbank_id) AS primary_atc_l1,
       (SELECT string_agg(DISTINCT b.l4, '|' ORDER BY b.l4) FROM bridge_drug_atc b WHERE b.drugbank_id = d.drugbank_id) AS atc_l4_codes
FROM stg_drugbank d
WHERE d.drugbank_id IN (SELECT drugbank_id FROM xwalk_stitch_drugbank)
  AND d.drugbank_id IN (SELECT drugbank_id FROM fact_drug_side_effect);
