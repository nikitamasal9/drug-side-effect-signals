"""Step 2: statistics that SQL alone can't do comfortably.

* Disproportionality: which side effects are over-represented in a drug class?
* Method check: does it recover textbook class effects?
* Drug similarity: which drugs have the most similar side-effect profiles?
"""
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import false_discovery_control, hypergeom

from config import (DB_PATH, FDR_ALPHA, KNOWN_CLASS_EFFECTS, MIN_DRUGS_IN_CLASS,
                    MIN_DRUGS_WITH_SE, MIN_ODDS_RATIO)


def load_matrix(con):
    """Binary drug x side-effect matrix (rows = drugs, cols = side effects)."""
    pairs = con.execute("SELECT drugbank_id, side_effect_id FROM fact_drug_side_effect").df()
    drugs = np.sort(pairs.drugbank_id.unique())
    ses = np.sort(pairs.side_effect_id.unique())
    d_idx = pd.Series(np.arange(len(drugs)), index=drugs)
    s_idx = pd.Series(np.arange(len(ses)), index=ses)
    m = np.zeros((len(drugs), len(ses)), dtype=np.float32)
    m[d_idx[pairs.drugbank_id].values, s_idx[pairs.side_effect_id].values] = 1
    return m, drugs, ses


def class_signals(con) -> pd.DataFrame:
    """One-sided Fisher's exact test for every (drug class, side effect) pair.

    Universe = drugs that have at least one ATC class. For a class C and side effect S:
        a = drugs in C with S        b = drugs in C without S
        c = drugs outside C with S   d = drugs outside C without S
    """
    m, drugs, ses = load_matrix(con)
    bridge = con.execute("""
        SELECT DISTINCT drugbank_id, 2 AS level, l2 AS atc_class FROM bridge_drug_atc
        UNION SELECT DISTINCT drugbank_id, 3, l3 FROM bridge_drug_atc
        UNION SELECT DISTINCT drugbank_id, 4, l4 FROM bridge_drug_atc
    """).df()
    bridge = bridge[bridge.drugbank_id.isin(drugs)]

    universe = np.isin(drugs, bridge.drugbank_id.unique())
    mu = m[universe]
    u_drugs = drugs[universe]
    N = mu.shape[0]
    se_totals = mu.sum(axis=0)                       # drugs (in universe) with each SE

    classes = (bridge.groupby(["level", "atc_class"]).drugbank_id.apply(set)
               .loc[lambda s: s.map(len) >= MIN_DRUGS_IN_CLASS])
    membership = np.array([[d in members for d in u_drugs] for members in classes.values],
                          dtype=np.float32)          # classes x drugs
    a = membership @ mu                              # classes x SEs: drugs in class with SE
    n_class = membership.sum(axis=1, keepdims=True)

    ci, si = np.nonzero(a >= MIN_DRUGS_WITH_SE)
    a_ = a[ci, si]
    n_ = n_class[ci, 0]
    K = se_totals[si]
    b_, c_ = n_ - a_, K - a_
    d_ = N - n_ - c_

    p = hypergeom.sf(a_ - 1, N, K, n_)               # P(X >= a): one-sided Fisher
    q = false_discovery_control(p, method="bh")
    # Haldane-Anscombe correction keeps OR finite when a cell is 0
    log_or = np.log(((a_ + .5) * (d_ + .5)) / ((b_ + .5) * (c_ + .5)))
    se_log = np.sqrt(1/(a_+.5) + 1/(b_+.5) + 1/(c_+.5) + 1/(d_+.5))

    out = pd.DataFrame({
        "level": classes.index.get_level_values(0)[ci],
        "atc_class": classes.index.get_level_values(1)[ci],
        "side_effect_id": ses[si],
        "drugs_in_class": n_.astype(int),
        "drugs_in_class_with_se": a_.astype(int),
        "pct_in_class": a_ / n_,
        "pct_outside_class": c_ / (N - n_),
        "odds_ratio": np.exp(log_or),
        "or_ci_low": np.exp(log_or - 1.96 * se_log),
        "or_ci_high": np.exp(log_or + 1.96 * se_log),
        "p_value": p,
        "q_value": q,
    })
    out["lift"] = out.pct_in_class / out.pct_outside_class.replace(0, np.nan)
    out["is_signal"] = (out.q_value < FDR_ALPHA) & (out.odds_ratio >= MIN_ODDS_RATIO)
    names = con.execute("""SELECT side_effect_id, side_effect_name, is_serious FROM dim_side_effect""").df()
    cls = con.execute("SELECT atc_class, class_name FROM dim_atc_class").df()
    out = out.merge(names, on="side_effect_id").merge(cls, on="atc_class", how="left")
    print(f"  tested {len(out):,} class/side-effect pairs across {len(classes)} classes "
          f"({N} drugs); {out.is_signal.sum():,} signals at FDR<{FDR_ALPHA}, OR>={MIN_ODDS_RATIO}")
    return out.sort_values(["is_signal", "q_value", "odds_ratio"], ascending=[False, True, False])


def validate_known_effects(signals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for atc, pt, label in KNOWN_CLASS_EFFECTS:
        hit = signals[(signals.atc_class == atc) & (signals.side_effect_name == pt)]
        if hit.empty:
            rows.append({"atc_class": atc, "class_label": label, "side_effect_name": pt,
                         "status": "not tested (too few drugs)", "odds_ratio": np.nan,
                         "q_value": np.nan, "pct_in_class": np.nan, "pct_outside_class": np.nan})
        else:
            h = hit.iloc[0]
            rows.append({"atc_class": atc, "class_label": label, "side_effect_name": pt,
                         "status": "recovered" if h.is_signal else "not significant",
                         "odds_ratio": h.odds_ratio, "q_value": h.q_value,
                         "pct_in_class": h.pct_in_class, "pct_outside_class": h.pct_outside_class})
    df = pd.DataFrame(rows)
    tested = df[df.status != "not tested (too few drugs)"]
    print(f"  known class effects recovered: {(df.status == 'recovered').sum()} of {len(tested)} testable "
          f"({len(df)} listed)")
    return df


def drug_similarity(con, top_k: int = 5) -> tuple[pd.DataFrame, dict]:
    """Jaccard similarity of side-effect profiles; top-k neighbours for every drug."""
    m, drugs, _ = load_matrix(con)
    inter = m @ m.T
    sizes = m.sum(axis=1)
    jac = inter / (sizes[:, None] + sizes[None, :] - inter)
    np.fill_diagonal(jac, -1)
    idx = np.argsort(-jac, axis=1)[:, :top_k]
    rows = [{"drugbank_id": drugs[i], "rank": r + 1, "similar_drugbank_id": drugs[j],
             "jaccard": float(jac[i, j])} for i in range(len(drugs)) for r, j in enumerate(idx[i])]
    nn = pd.DataFrame(rows)

    # Does the nearest neighbour share a pharmacological subgroup (ATC level 4)?
    l4 = (con.execute("SELECT DISTINCT drugbank_id, l4 FROM bridge_drug_atc").df()
          .groupby("drugbank_id").l4.apply(set))
    top1 = nn[nn["rank"] == 1]
    eligible = top1[top1.drugbank_id.isin(l4.index) & top1.similar_drugbank_id.isin(l4.index)]
    shares = eligible.apply(lambda r: bool(l4[r.drugbank_id] & l4[r.similar_drugbank_id]), axis=1)
    # Baseline: chance that two random drugs (with ATC) share a level-4 class
    rng = np.random.default_rng(42)
    ids = l4.index.to_numpy()
    pairs = rng.choice(ids, size=(20000, 2))
    pairs = pairs[pairs[:, 0] != pairs[:, 1]]
    baseline = np.mean([bool(l4[x] & l4[y]) for x, y in pairs])
    stats = {"nn_same_class_rate": float(shares.mean()), "random_same_class_rate": float(baseline),
             "n_drugs_evaluated": int(len(eligible))}
    print(f"  nearest neighbour shares an ATC level-4 class: {stats['nn_same_class_rate']:.1%} "
          f"vs {stats['random_same_class_rate']:.1%} for random pairs")
    return nn, stats


def main(con=None):
    con = con or duckdb.connect(str(DB_PATH))
    print("Running analysis")
    signals = class_signals(con)
    known = validate_known_effects(signals)
    nn, sim_stats = drug_similarity(con)
    con.execute("CREATE OR REPLACE TABLE an_class_signals AS SELECT * FROM signals")
    con.execute("CREATE OR REPLACE TABLE an_known_effect_check AS SELECT * FROM known")
    con.execute("CREATE OR REPLACE TABLE an_drug_neighbours AS SELECT * FROM nn")
    return signals, known, nn, sim_stats


if __name__ == "__main__":
    main()
