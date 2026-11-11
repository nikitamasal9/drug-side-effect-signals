"""Download the nine public source files into data/raw/ (works on Windows, macOS and Linux).

Run from the project root:   python scripts/00_download.py
"""
from pathlib import Path
from urllib.request import urlopen

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

SIDER = "https://raw.githubusercontent.com/dhimmel/SIDER4/master"
DRUGBANK = "https://raw.githubusercontent.com/dhimmel/drugbank/gh-pages"
ATC = "https://raw.githubusercontent.com/fabkury/atcd/master"

FILES = {
    # SIDER 4.1: side effects, frequencies, indications (CC BY-NC-SA 4.0)
    "meddra_all_se.tsv.gz":          f"{SIDER}/download/meddra_all_se.tsv.gz",
    "meddra_freq.tsv.gz":            f"{SIDER}/download/meddra_freq.tsv.gz",
    "meddra_all_indications.tsv.gz": f"{SIDER}/download/meddra_all_indications.tsv.gz",
    "sider_drugbank_crosswalk.tsv":  f"{SIDER}/data/indications.tsv",
    # DrugBank extract: names, ATC codes, PubChem mappings
    "drugbank.tsv":                  f"{DRUGBANK}/data/drugbank.tsv",
    "drugbank_pubchem_inchi.tsv":    f"{DRUGBANK}/data/pubchem-mapping.tsv",
    "drugbank_pubchem_unichem.tsv":  f"{DRUGBANK}/data/mapping/pubchem.tsv",
    # WHO ATC classification: current release + older one for retired codes
    "who_atc_2026.csv":              f"{ATC}/WHO%20ATC-DDD%202026-04-25.csv",
    "who_atc_2021.csv":              f"{ATC}/WHO%20ATC-DDD%202021-12-03.csv",
}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for i, (name, url) in enumerate(FILES.items(), 1):
        target = RAW / name
        if target.exists() and target.stat().st_size > 0:
            print(f"[{i}/{len(FILES)}] {name} already there, skipping")
            continue
        print(f"[{i}/{len(FILES)}] downloading {name} ...", end=" ", flush=True)
        with urlopen(url, timeout=120) as resp:
            data = resp.read()
        target.write_bytes(data)
        print(f"{len(data) / 1e6:.1f} MB")
    print(f"Done. Files are in {RAW}")


if __name__ == "__main__":
    main()