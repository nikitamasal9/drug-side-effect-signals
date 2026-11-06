"""Step 3: write CSVs for Tableau / Power BI and compact data files for the web dashboard."""
import json

from config import BI_EXPORTS, DASHBOARD, FDR_ALPHA, MIN_ODDS_RATIO, OUTPUTS

STAR_TABLES = ["dim_drug", "dim_side_effect", "dim_condition", "dim_atc_class",
               "bridge_drug_atc", "fact_drug_side_effect", "fact_drug_indication",
               "xwalk_stitch_drugbank", "an_class_signals", "an_known_effect_check",
               "an_drug_neighbours"]


# Tables exported with extra lookup columns so BI tools don't need another join
BI_OVERRIDES = {
    "an_drug_neighbours": """SELECT n.*, d.drug_name AS similar_drug_name
                             FROM an_drug_neighbours n
                             JOIN dim_drug d ON d.drugbank_id = n.similar_drugbank_id
                             ORDER BY n.drugbank_id, n.rank""",
}


def bi_exports(con, view_names):
    """Every model table and analysis view as a CSV — import these into Tableau or Power BI."""
    for t in STAR_TABLES + [f"an_{n}" for n in view_names]:
        sql = BI_OVERRIDES.get(t, f"SELECT * FROM {t}")
        con.execute(f"COPY ({sql}) TO '{(BI_EXPORTS / f'{t}.csv').as_posix()}' (HEADER)")
    print(f"  wrote {len(STAR_TABLES) + len(view_names)} CSVs to outputs/bi_exports/")


def _csv(con, sql, name):
    out = DASHBOARD / "data" / name
    con.execute(f"COPY ({sql}) TO '{out.as_posix()}' (HEADER)")
    return out


def dashboard_data(con, sim_stats):
    (DASHBOARD / "data").mkdir(parents=True, exist_ok=True)
    q = lambda s: con.execute(s).fetchone()[0]
    known = con.execute("SELECT status, COUNT(*) FROM an_known_effect_check GROUP BY 1").fetchall()
    known = dict(known)
    kpis = {
        "drugs": q("SELECT COUNT(*) FROM dim_drug"),
        "drugs_with_class": q("SELECT COUNT(*) FROM dim_drug WHERE primary_atc_l1 IS NOT NULL"),
        "side_effects": q("SELECT COUNT(*) FROM dim_side_effect"),
        "drug_side_effect_pairs": q("SELECT COUNT(*) FROM fact_drug_side_effect"),
        "pairs_with_placebo_rate": q("SELECT COUNT(*) FROM fact_drug_side_effect WHERE excess_over_placebo IS NOT NULL"),
        "classes_tested": q("SELECT COUNT(DISTINCT atc_class) FROM an_class_signals"),
        "pairs_tested": q("SELECT COUNT(*) FROM an_class_signals"),
        "signals": q("SELECT COUNT(*) FROM an_class_signals WHERE is_signal"),
        "known_recovered": known.get("recovered", 0),
        "known_testable": known.get("recovered", 0) + known.get("not significant", 0),
        "nn_same_class_rate": round(sim_stats["nn_same_class_rate"], 4),
        "random_same_class_rate": round(sim_stats["random_same_class_rate"], 4),
        "mapping_rate": round(q("SELECT COUNT(DISTINCT s.stitch_flat) FROM stg_sider_se s JOIN xwalk_stitch_drugbank USING (stitch_flat)")
                              / q("SELECT COUNT(DISTINCT stitch_flat) FROM stg_sider_se"), 4),
        "fdr_alpha": FDR_ALPHA,
        "min_odds_ratio": MIN_ODDS_RATIO,
    }
    (DASHBOARD / "data" / "kpis.json").write_text(json.dumps([kpis], indent=1))
    (OUTPUTS / "key_numbers.json").write_text(json.dumps(kpis | sim_stats, indent=1))

    _csv(con, "SELECT * FROM an_q01_data_funnel", "funnel.csv")
    _csv(con, """SELECT atc_class || '|' || side_effect_id AS signal_id, level, atc_class, class_name,
                        side_effect_name, is_serious, drugs_in_class, drugs_in_class_with_se,
                        ROUND(pct_in_class, 4) AS pct_in_class, ROUND(pct_outside_class, 4) AS pct_outside_class,
                        ROUND(odds_ratio, 2) AS odds_ratio, q_value
                 FROM an_class_signals WHERE is_signal""", "signals.csv")
    _csv(con, """SELECT atc_class, class_label, side_effect_name, status, ROUND(odds_ratio, 1) AS odds_ratio,
                        q_value, ROUND(pct_in_class, 4) AS pct_in_class, ROUND(pct_outside_class, 4) AS pct_outside_class
                 FROM an_known_effect_check""", "known_effects.csv")
    _csv(con, "SELECT * FROM an_q04_class_heatmap", "heatmap.csv")
    _csv(con, "SELECT * FROM an_q03_burden_by_class", "burden.csv")
    _csv(con, """SELECT drugbank_id, drug_name, n_side_effects, n_serious_side_effects, n_indications,
                        primary_atc_l1, atc_l4_codes FROM dim_drug ORDER BY drug_name""", "drugs.csv")
    # Drug explorer: only the rows it shows (serious side effects, or ones with a measured rate)
    _csv(con, """SELECT f.drugbank_id, f.side_effect_id, s.side_effect_name, s.is_serious::INT AS is_serious,
                        ROUND(f.freq_drug, 4) AS freq_drug, ROUND(f.freq_placebo, 4) AS freq_placebo,
                        f.postmarketing_only::INT AS postmarketing_only
                 FROM fact_drug_side_effect f JOIN dim_side_effect s USING (side_effect_id)
                 WHERE s.is_serious OR f.freq_drug IS NOT NULL""", "drug_side_effects.csv")
    _csv(con, """SELECT n.drugbank_id, n.rank, n.similar_drugbank_id, d.drug_name AS similar_drug_name,
                        ROUND(n.jaccard, 3) AS jaccard
                 FROM an_drug_neighbours n JOIN dim_drug d ON d.drugbank_id = n.similar_drugbank_id""",
         "neighbours.csv")
    _csv(con, """SELECT i.drugbank_id, c.condition_name FROM fact_drug_indication i
                 JOIN dim_condition c USING (condition_id)""", "indications.csv")
    _csv(con, "SELECT * FROM an_q08_condition_options", "condition_options.csv")
    _csv(con, "SELECT * FROM an_q06_nocebo_effects", "nocebo.csv")
    _csv(con, "SELECT * FROM an_q07_postmarketing_serious", "postmarketing_serious.csv")
    print("  wrote dashboard data to dashboard/data/")
