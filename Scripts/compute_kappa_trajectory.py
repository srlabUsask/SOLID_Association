"""
Compute inter-rater weighted Cohen's kappa across annotation rounds.

Reads round-by-round annotation databases and outputs per-principle
weighted kappa per round. Round 3 only re-annotated DIP, so SRP and
OCP are not computed for round 3.


"""

import sqlite3
import pandas as pd
from sklearn.metrics import cohen_kappa_score

VALIDATION_DIR = "validation_toolkit"

DBS = {
    "round1": {
        "rater_a": f"{VALIDATION_DIR}/annotations_rater_a.db",
        "rater_b": f"{VALIDATION_DIR}/annotations_rater_b.db",
    },
    "round2": {
        "rater_a": f"{VALIDATION_DIR}/round2_rater_a.db",
        "rater_b": f"{VALIDATION_DIR}/round2_rater_b.db",
    },
    "round3": {
        "rater_a": f"{VALIDATION_DIR}/round3_rater_a.db",
        "rater_b": f"{VALIDATION_DIR}/round3_rater_b.db",
    },
}

def load_db(path):
    conn = sqlite3.connect(path)
    df = pd.read_sql_query("SELECT * FROM annotations", conn)
    conn.close()
    return df

def kappa_for_principle(a, b, principle):
    """Weighted (linear) kappa across cases both annotators scored."""
    col = f"{principle}_score"
    if col not in a.columns or col not in b.columns:
        return None, 0
    sub_a = a[["method_id", col]].dropna()
    sub_b = b[["method_id", col]].dropna()
    merged = sub_a.merge(sub_b, on="method_id", suffixes=("_a", "_b"))
    if len(merged) < 10:
        return None, len(merged)
    k = cohen_kappa_score(
        merged[f"{col}_a"].astype(int),
        merged[f"{col}_b"].astype(int),
        weights="linear",
    )
    return k, len(merged)

def main():
    rows = []
    for round_name, paths in DBS.items():
        try:
            a = load_db(paths["rater_a"])
            b = load_db(paths["rater_b"])
        except Exception as e:
            print(f"Skipping {round_name}: {e}")
            continue
        for principle in ["srp", "ocp", "dip"]:
            k, n = kappa_for_principle(a, b, principle)
            rows.append({
                "round": round_name,
                "principle": principle.upper(),
                "weighted_kappa": k,
                "n": n,
            })
            if k is not None:
                print(f"{round_name} {principle.upper()}: kappa_w = {k:.3f} (n={n})")
            else:
                print(f"{round_name} {principle.upper()}: insufficient data (n={n})")

    df = pd.DataFrame(rows)
    out = "Results/kappa_trajectory.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote: {out}")

if __name__ == "__main__":
    main()