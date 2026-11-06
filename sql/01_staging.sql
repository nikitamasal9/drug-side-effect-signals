-- =============================================================================
-- 01_staging.sql  —  Load raw files into typed staging tables (no business logic)
-- Run by src/run_pipeline.py with DuckDB. {RAW} is replaced with data/raw.
-- =============================================================================

-- SIDER side effects: one row per (compound, label term, MedDRA level)
CREATE OR REPLACE TABLE stg_sider_se AS
SELECT * FROM read_csv('{RAW}/meddra_all_se.tsv.gz', delim='\t', header=false, quote='',
    columns={'stitch_flat':'VARCHAR','stitch_stereo':'VARCHAR','umls_cui_label':'VARCHAR',
             'meddra_type':'VARCHAR','umls_cui_meddra':'VARCHAR','side_effect_name':'VARCHAR'});

-- SIDER frequencies: drug arm and placebo arm, possibly several per pair
CREATE OR REPLACE TABLE stg_sider_freq AS
SELECT * FROM read_csv('{RAW}/meddra_freq.tsv.gz', delim='\t', header=false, quote='',
    columns={'stitch_flat':'VARCHAR','stitch_stereo':'VARCHAR','umls_cui_label':'VARCHAR',
             'placebo':'VARCHAR','freq_description':'VARCHAR','freq_lower':'DOUBLE','freq_upper':'DOUBLE',
             'meddra_type':'VARCHAR','umls_cui_meddra':'VARCHAR','side_effect_name':'VARCHAR'});

-- SIDER indications (the "medical conditions" a drug is labelled for)
CREATE OR REPLACE TABLE stg_sider_indications AS
SELECT * FROM read_csv('{RAW}/meddra_all_indications.tsv.gz', delim='\t', header=false, quote='',
    columns={'stitch_flat':'VARCHAR','umls_cui_label':'VARCHAR','detection_method':'VARCHAR',
             'concept_name':'VARCHAR','meddra_type':'VARCHAR','umls_cui_meddra':'VARCHAR',
             'meddra_name':'VARCHAR'});

-- DrugBank drug master (names, type, approval groups, ATC codes as pipe-delimited list)
CREATE OR REPLACE TABLE stg_drugbank AS
SELECT drugbank_id, name, type, groups, atc_codes, categories
FROM read_csv('{RAW}/drugbank.tsv', delim='\t', header=true, all_varchar=true);

-- Three alternative ways to connect a SIDER compound to a DrugBank drug
CREATE OR REPLACE TABLE stg_map_inchi AS
SELECT drugbank_id, CAST(pubchem_cid AS BIGINT) AS pubchem_cid
FROM read_csv('{RAW}/drugbank_pubchem_inchi.tsv', delim='\t', header=true, all_varchar=true);

CREATE OR REPLACE TABLE stg_map_unichem AS
SELECT drugbank_id, TRY_CAST(pubchem_id AS BIGINT) AS pubchem_cid
FROM read_csv('{RAW}/drugbank_pubchem_unichem.tsv', delim='\t', header=true, all_varchar=true);

CREATE OR REPLACE TABLE stg_map_curated AS
SELECT DISTINCT stitch_id_flat AS stitch_flat, drugbank_id
FROM read_csv('{RAW}/sider_drugbank_crosswalk.tsv', delim='\t', header=true, all_varchar=true);

-- WHO ATC hierarchy: current release + an older one for codes WHO has since retired
CREATE OR REPLACE TABLE stg_atc_2026 AS
SELECT DISTINCT atc_code, atc_name FROM read_csv('{RAW}/who_atc_2026.csv', header=true, all_varchar=true);
CREATE OR REPLACE TABLE stg_atc_2021 AS
SELECT DISTINCT atc_code, atc_name FROM read_csv('{RAW}/who_atc_2021.csv', header=true, all_varchar=true);
