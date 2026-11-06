#!/usr/bin/env bash
# Downloads the three public sources this project uses into data/raw/.
# Run from the project root:  bash scripts/00_download.sh
set -euo pipefail

RAW="data/raw"
TMP="$(mktemp -d)"
mkdir -p "$RAW"

echo "1/3  SIDER 4.1 (drug -> side effect, frequency, indication; via dhimmel/SIDER4 mirror)"
git clone --depth 1 https://github.com/dhimmel/SIDER4.git "$TMP/SIDER4"
cp "$TMP/SIDER4/download/meddra_all_se.tsv.gz"          "$RAW/"
cp "$TMP/SIDER4/download/meddra_freq.tsv.gz"            "$RAW/"
cp "$TMP/SIDER4/download/meddra_all_indications.tsv.gz" "$RAW/"
cp "$TMP/SIDER4/data/indications.tsv"                   "$RAW/sider_drugbank_crosswalk.tsv"

echo "2/3  DrugBank extract (names, ATC codes) + PubChem mappings (via dhimmel/drugbank)"
git clone --depth 1 https://github.com/dhimmel/drugbank.git "$TMP/drugbank"
cp "$TMP/drugbank/data/drugbank.tsv"         "$RAW/"
cp "$TMP/drugbank/data/pubchem-mapping.tsv"  "$RAW/drugbank_pubchem_inchi.tsv"
cp "$TMP/drugbank/data/mapping/pubchem.tsv"  "$RAW/drugbank_pubchem_unichem.tsv"

echo "3/3  WHO ATC classification (current 2026 release + 2021 release for retired codes; via fabkury/atcd)"
git clone --depth 1 https://github.com/fabkury/atcd.git "$TMP/atcd"
cp "$TMP/atcd/WHO ATC-DDD 2026-04-25.csv" "$RAW/who_atc_2026.csv"
cp "$TMP/atcd/WHO ATC-DDD 2021-12-03.csv" "$RAW/who_atc_2021.csv"

rm -rf "$TMP"
echo "Done. Files in $RAW:"
ls -lh "$RAW"
