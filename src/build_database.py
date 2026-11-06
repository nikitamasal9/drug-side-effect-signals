"""Step 1: load raw files and build the DuckDB star schema."""
import duckdb
import pandas as pd

from config import DB_PATH, PROCESSED, RAW, SERIOUS_PTS, SQL


def run_sql_file(con: duckdb.DuckDBPyConnection, name: str) -> None:
    sql = (SQL / name).read_text().replace("{RAW}", RAW.as_posix())
    con.execute(sql)
    print(f"  ran {name}")


def data_quality_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Assertions that would catch a broken merge. Fails loudly instead of silently."""
    checks = {
        "one DrugBank drug per SIDER compound":
            "SELECT COUNT(*) FROM (SELECT stitch_flat FROM xwalk_stitch_drugbank GROUP BY 1 HAVING COUNT(*) > 1)",
        "no duplicate drug x side-effect rows":
            "SELECT COUNT(*) FROM (SELECT drugbank_id, side_effect_id FROM fact_drug_side_effect GROUP BY 1,2 HAVING COUNT(*) > 1)",
        "every fact side effect exists in dim_side_effect":
            "SELECT COUNT(*) FROM fact_drug_side_effect f ANTI JOIN dim_side_effect s USING (side_effect_id)",
        "every fact drug exists in dim_drug":
            "SELECT COUNT(*) FROM fact_drug_side_effect f ANTI JOIN dim_drug d USING (drugbank_id)",
        "frequencies are valid proportions (0-1)":
            "SELECT COUNT(*) FROM fact_drug_side_effect WHERE freq_drug < 0 OR freq_drug > 1 OR freq_placebo < 0 OR freq_placebo > 1",
        "every ATC level-1 class has a name":
            "SELECT COUNT(*) FROM bridge_drug_atc WHERE l1_name IS NULL",
    }
    rows = []
    for name, q in checks.items():
        bad = con.execute(q).fetchone()[0]
        rows.append({"check": name, "failing_rows": bad, "passed": bad == 0})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    if not df.passed.all():
        raise AssertionError("Data quality checks failed — see table above.")
    return df


def main() -> duckdb.DuckDBPyConnection:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    print("Building database")
    run_sql_file(con, "01_staging.sql")
    con.execute("CREATE OR REPLACE TABLE ref_serious_pts AS SELECT UNNEST(?::VARCHAR[]) AS pt_name",
                [sorted(SERIOUS_PTS)])
    run_sql_file(con, "02_crosswalk.sql")
    run_sql_file(con, "03_model.sql")
    print("Data quality checks")
    data_quality_checks(con)
    return con


if __name__ == "__main__":
    main().close()
