-- =============================================================================
-- 02_crosswalk.sql  —  The hard part: connect SIDER compounds to DrugBank drugs
--
-- Problem: SIDER identifies drugs with STITCH IDs ("CID100047725"), DrugBank
-- uses "DB00014", and the ATC drug classes hang off DrugBank. There is no
-- shared key, so we build one through PubChem compound IDs:
--   STITCH flat  "CID1" + 8-digit PubChem CID (stereochemistry removed)
--   STITCH stereo"CID0" + 8-digit PubChem CID (specific stereoisomer)
-- Three mapping sources are tried in priority order:
--   1. exact InChI match DrugBank -> PubChem   (most precise)
--   2. curated SIDER->DrugBank crosswalk        (hand-checked by dhimmel)
--   3. UniChem connectivity match              (broadest, can over-match salts)
-- =============================================================================

-- Every SIDER compound seen in any file, with both PubChem IDs decoded
CREATE OR REPLACE TABLE int_sider_compounds AS
WITH ids AS (
    SELECT stitch_flat, stitch_stereo FROM stg_sider_se
    UNION SELECT stitch_flat, stitch_stereo FROM stg_sider_freq
    UNION SELECT stitch_flat, NULL FROM stg_sider_indications
)
SELECT DISTINCT
    stitch_flat,
    stitch_stereo,
    CAST(substr(stitch_flat, 5) AS BIGINT)   AS pubchem_flat,
    CAST(substr(stitch_stereo, 5) AS BIGINT) AS pubchem_stereo
FROM ids;

-- All candidate (stitch_flat -> drugbank_id) links, tagged with their source rank
CREATE OR REPLACE TABLE int_map_candidates AS
SELECT DISTINCT c.stitch_flat, m.drugbank_id, 1 AS source_rank, 'inchi_exact' AS map_source
FROM int_sider_compounds c
JOIN stg_map_inchi m ON m.pubchem_cid IN (c.pubchem_flat, c.pubchem_stereo)
UNION
SELECT DISTINCT stitch_flat, drugbank_id, 2, 'curated_crosswalk' FROM stg_map_curated
UNION
SELECT DISTINCT c.stitch_flat, m.drugbank_id, 3, 'unichem_connectivity'
FROM int_sider_compounds c
JOIN stg_map_unichem m ON m.pubchem_cid IN (c.pubchem_flat, c.pubchem_stereo);

-- Pick exactly one DrugBank drug per SIDER compound.
-- Tie-breakers inside the best source: has ATC codes > approved > lowest ID.
CREATE OR REPLACE TABLE xwalk_stitch_drugbank AS
SELECT
    c.stitch_flat,
    c.drugbank_id,
    c.map_source,
    COUNT(*) OVER (PARTITION BY c.stitch_flat, c.source_rank) AS n_candidates_same_rank
FROM int_map_candidates c
JOIN stg_drugbank d USING (drugbank_id)
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY c.stitch_flat
    ORDER BY c.source_rank,
             (d.atc_codes IS NOT NULL) DESC,
             (d.groups LIKE '%approved%') DESC,
             c.drugbank_id
) = 1;

-- Mapping QA: how many SIDER compounds made it, and how
CREATE OR REPLACE TABLE qa_mapping_summary AS
SELECT
    COALESCE(x.map_source, 'UNMAPPED') AS map_source,
    COUNT(DISTINCT s.stitch_flat)      AS sider_compounds
FROM (SELECT DISTINCT stitch_flat FROM int_sider_compounds) s
LEFT JOIN xwalk_stitch_drugbank x USING (stitch_flat)
GROUP BY 1
ORDER BY 2 DESC;
