-- =============================================================================
-- 04_analysis_queries.sql  —  Business questions answered in SQL
-- Each query starts with "-- name: <view_name>". run_pipeline.py turns each
-- into a view (an_*) and exports it to outputs/bi_exports/<view_name>.csv.
-- =============================================================================

-- name: q01_data_funnel
-- How much data survives each step? (Shows the cost of the merge honestly.)
SELECT 1 AS step, 'SIDER compounds with side effects' AS stage, COUNT(DISTINCT stitch_flat) AS n FROM stg_sider_se
UNION ALL SELECT 2, 'Mapped to a DrugBank drug', COUNT(DISTINCT s.stitch_flat)
    FROM stg_sider_se s JOIN xwalk_stitch_drugbank USING (stitch_flat)
UNION ALL SELECT 3, 'Unique DrugBank drugs (after rolling up stereoisomers)', COUNT(*) FROM dim_drug
UNION ALL SELECT 4, 'Drugs with a WHO ATC class (used for class analysis)', COUNT(*) FROM dim_drug WHERE primary_atc_l1 IS NOT NULL
UNION ALL SELECT 5, 'Drugs with labelled indications', COUNT(DISTINCT drugbank_id) FROM fact_drug_indication
ORDER BY step;

-- name: q02_top_side_effects
-- Which side effects appear on the most drug labels?
SELECT s.side_effect_name,
       s.is_serious,
       s.n_drugs,
       ROUND(s.n_drugs / (SELECT COUNT(*) FROM dim_drug), 4) AS pct_of_drugs
FROM dim_side_effect s
ORDER BY s.n_drugs DESC
LIMIT 40;

-- name: q03_burden_by_class
-- Side-effect burden by anatomical group (ATC level 1).
SELECT b.l1 AS atc_l1,
       b.l1_name,
       COUNT(DISTINCT d.drugbank_id)                        AS n_drugs,
       MEDIAN(d.n_side_effects)                             AS median_side_effects,
       ROUND(AVG(d.n_side_effects), 1)                      AS avg_side_effects,
       MEDIAN(d.n_serious_side_effects)                     AS median_serious,
       ROUND(AVG((d.n_serious_side_effects > 0)::INT), 3)   AS pct_with_any_serious
FROM dim_drug d
JOIN (SELECT DISTINCT drugbank_id, l1, l1_name FROM bridge_drug_atc) b USING (drugbank_id)
GROUP BY 1, 2
ORDER BY n_drugs DESC;

-- name: q04_class_heatmap
-- % of drugs in each anatomical group that list each of the 25 most common side effects.
WITH top_se AS (SELECT side_effect_id FROM dim_side_effect ORDER BY n_drugs DESC LIMIT 25),
grp AS (SELECT DISTINCT drugbank_id, l1, l1_name FROM bridge_drug_atc),
grp_size AS (SELECT l1, COUNT(*) AS n FROM grp GROUP BY 1)
SELECT g.l1 AS atc_l1, g.l1_name, s.side_effect_name,
       ROUND(COUNT(f.drugbank_id) / ANY_VALUE(gs.n), 4) AS pct_of_drugs
FROM grp g
CROSS JOIN top_se t
JOIN dim_side_effect s ON s.side_effect_id = t.side_effect_id
JOIN grp_size gs ON gs.l1 = g.l1
LEFT JOIN fact_drug_side_effect f ON f.drugbank_id = g.drugbank_id AND f.side_effect_id = t.side_effect_id
GROUP BY 1, 2, 3;

-- name: q05_placebo_adjusted
-- Where trial data gives both a drug-arm and placebo-arm rate: biggest excess risks.
SELECT d.drug_name, s.side_effect_name, s.is_serious,
       ROUND(f.freq_drug, 4)            AS freq_drug,
       ROUND(f.freq_placebo, 4)         AS freq_placebo,
       ROUND(f.excess_over_placebo, 4)  AS excess_over_placebo,
       ROUND(f.freq_drug / NULLIF(f.freq_placebo, 0), 2) AS relative_risk
FROM fact_drug_side_effect f
JOIN dim_drug d USING (drugbank_id)
JOIN dim_side_effect s USING (side_effect_id)
WHERE f.excess_over_placebo IS NOT NULL
ORDER BY f.excess_over_placebo DESC;

-- name: q06_nocebo_effects
-- Side effects that are reported about as often on placebo as on the drug
-- (excess within ±1 point across >= 10 drugs) — likely not caused by the drug.
SELECT s.side_effect_name,
       COUNT(*)                                   AS n_drugs_with_both_arms,
       ROUND(MEDIAN(f.freq_drug), 4)              AS median_freq_drug,
       ROUND(MEDIAN(f.freq_placebo), 4)           AS median_freq_placebo,
       ROUND(MEDIAN(f.excess_over_placebo), 4)    AS median_excess
FROM fact_drug_side_effect f
JOIN dim_side_effect s USING (side_effect_id)
WHERE f.excess_over_placebo IS NOT NULL
GROUP BY 1
HAVING COUNT(*) >= 10
ORDER BY median_excess ASC;

-- name: q07_postmarketing_serious
-- Serious side effects that only appear in post-marketing reports (missed in trials).
SELECT s.side_effect_name,
       COUNT(*) FILTER (WHERE f.postmarketing_only)  AS n_drugs_postmarketing_only,
       COUNT(*)                                      AS n_drugs_total,
       ROUND(COUNT(*) FILTER (WHERE f.postmarketing_only) / COUNT(*), 3) AS share_postmarketing_only
FROM fact_drug_side_effect f
JOIN dim_side_effect s USING (side_effect_id)
WHERE s.is_serious
GROUP BY 1
HAVING COUNT(*) >= 20
ORDER BY share_postmarketing_only DESC;

-- name: q08_condition_options
-- For each condition with >= 3 approved labelled drugs: compare the treatment options.
WITH opts AS (
    SELECT c.condition_id, c.condition_name, i.drugbank_id
    FROM dim_condition c JOIN fact_drug_indication i USING (condition_id)
    JOIN dim_drug d USING (drugbank_id)
    WHERE d.approval_groups LIKE '%approved%'       -- skip experimental ingredients (e.g. glucose in IV fluids)
)
SELECT o.condition_name, d.drug_name, d.drugbank_id,
       d.n_side_effects, d.n_serious_side_effects,
       RANK() OVER (PARTITION BY o.condition_id ORDER BY d.n_serious_side_effects, d.n_side_effects) AS burden_rank,
       COUNT(*) OVER (PARTITION BY o.condition_id) AS n_options
FROM opts o JOIN dim_drug d USING (drugbank_id)
QUALIFY COUNT(*) OVER (PARTITION BY o.condition_id) >= 3
ORDER BY o.condition_name, burden_rank;

-- name: q09_label_length_check
-- Caveat check: do drugs with more indications / newer, heavily-trialled drugs list more side effects?
SELECT CASE WHEN n_side_effects < 50 THEN '1: <50'
            WHEN n_side_effects < 150 THEN '2: 50-149'
            WHEN n_side_effects < 300 THEN '3: 150-299'
            ELSE '4: 300+' END AS label_size_band,
       COUNT(*) AS n_drugs,
       ROUND(AVG(n_serious_side_effects), 1) AS avg_serious,
       ROUND(AVG(n_indications), 1) AS avg_indications
FROM dim_drug
GROUP BY 1 ORDER BY 1;
