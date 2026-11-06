"""Run the whole project end to end:  python src/run_pipeline.py

  1. build_database  -> data/processed/drug_safety.duckdb (staging, crosswalk, star schema, QA)
  2. analysis        -> class signals, method validation, drug similarity
  3. SQL questions   -> sql/04_analysis_queries.sql as views
  4. exports         -> outputs/bi_exports/*.csv (Tableau / Power BI), dashboard/data/, outputs/figures/
"""
import json
import re

import build_database
import analysis
import export
import figures
from config import BI_EXPORTS, SQL


def run_named_queries(con) -> list[str]:
    text = (SQL / "04_analysis_queries.sql").read_text()
    blocks = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)[1:]
    names = []
    for name, body in zip(blocks[::2], blocks[1::2]):
        sql = body.strip().rstrip(";")
        con.execute(f"CREATE OR REPLACE VIEW an_{name} AS {sql}")
        names.append(name)
    print(f"  created {len(names)} analysis views")
    return names


def main():
    con = build_database.main()
    signals, known, nn, sim_stats = analysis.main(con)
    print("Running SQL analysis questions")
    names = run_named_queries(con)
    print("Exporting")
    BI_EXPORTS.mkdir(parents=True, exist_ok=True)
    export.bi_exports(con, names)
    export.dashboard_data(con, sim_stats)
    figures.main(con)
    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
