"""
analyze_final.py
----------------
Produces the FINAL agreement analysis after the iterative validation
process described in the methods section:

    Round 1: independent annotation of all 200 methods (already done)
    Calibration session: face-to-face resolution of all 35 extreme cases
    Round 2: independent re-annotation of methods with adjacent
             disagreements (different second-round databases per rater)
    PI tiebreaks: anything still in disagreement after round 2

This script takes all those inputs and produces:
    - inter-rater kappa using the FINAL round of each rater's score per
      method (round-2 if available, round-1 otherwise)
    - LLM-vs-consensus kappa, per-class metrics, confusion matrices

Inputs:
    - round1_results.csv (export from merged round-1 database, format
      from annotate.py --export)
    - round2_<rater>.db (one per rater, only contains re-annotated methods)
    - extreme_resolutions.csv (manual resolutions from session worksheet,
      columns: method_id, principle, agreed_score)
    - tiebreak.csv (any remaining disagreements adjudicated by PI,
      columns: method_id, principle, tiebreak_score)
    - holdout_sample.csv (for LLM scores)

Output:
    - final_agreement_summary.json
    - final_confusion_matrices.csv
    - per_method_final_scores.csv (audit trail)

Usage:
    python analyze_final.py \\
        --round1 ../results.csv \\
        --round2-rater-a ../round2_rater_a.db \\
        --round2-rater-b ../round2_rater_b.db \\
        --extreme ../extreme_resolutions.csv \\
        --tiebreak ../tiebreak.csv \\
        --sample ../holdout_sample.csv \\
        --output ../final_agreement_summary.json \\
        --confusion ../final_confusion_matrices.csv \\
        --audit ../per_method_final_scores.csv
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    cohen_kappa_score, confusion_matrix,
    precision_recall_fscore_support, accuracy_score,
)


PRINCIPLES = ["srp", "ocp", "dip"]
CLASSES = [0, 1, 2]
RATERS = ["annotator_a", "annotator_b"]


def load_round1(path: Path) -> pd.DataFrame:
    """Load round-1 long-form results from annotate.py --export."""
    df = pd.read_csv(path)
    df["method_id"] = df["method_id"].astype(str)
    keep = ["method_id", "rater"] + [
        f"{p}_score" for p in PRINCIPLES
    ] + [
        f"{p}_na" for p in PRINCIPLES
    ]
    return df[keep]


def load_round2(db_path: Path, rater_label: str) -> pd.DataFrame:
    """Load round-2 annotations from a per-rater SQLite db."""
    if not db_path.exists():
        return pd.DataFrame(columns=["method_id", "rater"] + [f"{p}_score" for p in PRINCIPLES] + [f"{p}_na" for p in PRINCIPLES])
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM annotations", conn)
    if df.empty:
        return df
    df["method_id"] = df["method_id"].astype(str)
    # Force rater label, in case students used a different identifier in round 2
    df["rater"] = rater_label
    return df[["method_id", "rater"] + [f"{p}_score" for p in PRINCIPLES] + [f"{p}_na" for p in PRINCIPLES]]


def merge_rounds(round1: pd.DataFrame, round2_by_rater: dict) -> pd.DataFrame:
    """For each (rater, method), prefer round-2 scores if available."""
    pieces = []
    for rater in RATERS:
        r1 = round1[round1["rater"] == rater].copy()
        r2 = round2_by_rater.get(rater, pd.DataFrame())
        r2 = r2[r2["rater"] == rater].copy() if not r2.empty else r2

        if r2.empty:
            r1["round"] = 1
            pieces.append(r1)
            continue

        r2["round"] = 2
        r2_ids = set(r2["method_id"])

        kept_r1 = r1[~r1["method_id"].isin(r2_ids)].copy()
        kept_r1["round"] = 1

        pieces.append(kept_r1)
        pieces.append(r2)

    return pd.concat(pieces, ignore_index=True)


def apply_resolutions(merged: pd.DataFrame,
                      extreme_path: Path | None,
                      tiebreak_path: Path | None) -> pd.DataFrame:
    """
    Build a per-(method, principle) consensus column.

    Rules, in priority order:
        1. PI tiebreak entry, if present (highest authority)
        2. Calibration session resolution (extreme), if present
        3. Both raters agree post-rounds: that value
        4. Both raters disagree post-rounds: NaN, flagged for re-tiebreak
    """
    # Pivot raters wide: one row per method with rater_a and rater_b score columns
    wide = pd.DataFrame({"method_id": merged["method_id"].unique()})

    for rater in RATERS:
        sub = merged[merged["rater"] == rater].copy()
        rename = {f"{p}_score": f"{p}_{rater}" for p in PRINCIPLES}
        rename.update({f"{p}_na": f"{p}_na_{rater}" for p in PRINCIPLES})
        rename["round"] = f"round_{rater}"
        sub = sub.rename(columns=rename)
        keep_cols = ["method_id"] + list(rename.values())
        wide = wide.merge(sub[keep_cols], on="method_id", how="left")

    # Load resolutions
    extreme = pd.read_csv(extreme_path) if extreme_path and extreme_path.exists() else pd.DataFrame()
    tiebreak = pd.read_csv(tiebreak_path) if tiebreak_path and tiebreak_path.exists() else pd.DataFrame()

    extreme_lookup = {}
    if not extreme.empty:
        for _, row in extreme.iterrows():
            extreme_lookup[(str(row["method_id"]), row["principle"])] = int(row["agreed_score"])

    tiebreak_lookup = {}
    if not tiebreak.empty:
        col = "tiebreak_score" if "tiebreak_score" in tiebreak.columns else "agreed_score"
        for _, row in tiebreak.iterrows():
            tiebreak_lookup[(str(row["method_id"]), row["principle"])] = int(row[col])

    # For each principle, compute consensus
    for p in PRINCIPLES:
        consensus = []
        provenance = []
        for _, row in wide.iterrows():
            mid = row["method_id"]
            key = (mid, p)

            # Priority 1: PI tiebreak
            if key in tiebreak_lookup:
                consensus.append(tiebreak_lookup[key])
                provenance.append("tiebreak")
                continue

            # Priority 2: extreme resolution from session
            if key in extreme_lookup:
                consensus.append(extreme_lookup[key])
                provenance.append("session")
                continue

            # Priority 3: rater agreement post-rounds
            sa = row.get(f"{p}_annotator_a")
            sb = row.get(f"{p}_annotator_b")
            na_a = row.get(f"{p}_na_annotator_a", 0) or 0
            na_b = row.get(f"{p}_na_annotator_b", 0) or 0

            if pd.isna(sa) or pd.isna(sb) or na_a or na_b:
                consensus.append(np.nan)
                provenance.append("missing")
                continue

            sa, sb = int(sa), int(sb)
            if sa == sb:
                consensus.append(sa)
                provenance.append("agreed")
            else:
                consensus.append(np.nan)
                provenance.append("unresolved")

        wide[f"{p}_consensus"] = consensus
        wide[f"{p}_provenance"] = provenance

    return wide


def compute_agreement(wide: pd.DataFrame, sample_with_llm: pd.DataFrame) -> dict:
    """Inter-rater kappa (using final per-rater scores) + LLM vs consensus."""
    summary = {}

    # Join LLM scores
    llm = sample_with_llm[["method_id"] + [f"{p}_score_llm" for p in PRINCIPLES]].copy()
    llm["method_id"] = llm["method_id"].astype(str)
    wide = wide.merge(llm, on="method_id", how="left")

    for p in PRINCIPLES:
        per_principle = {}

        # Inter-rater (using final scores after round 2)
        a_col = f"{p}_annotator_a"
        b_col = f"{p}_annotator_b"
        valid_pair = wide[[a_col, b_col]].dropna()
        if len(valid_pair) > 0:
            ya = valid_pair[a_col].astype(int)
            yb = valid_pair[b_col].astype(int)
            per_principle["inter_rater_final"] = {
                "n": int(len(valid_pair)),
                "kappa": float(cohen_kappa_score(ya, yb)),
                "weighted_kappa_linear": float(cohen_kappa_score(ya, yb, weights="linear")),
                "raw_agreement": float(accuracy_score(ya, yb)),
            }

        # LLM vs consensus
        cons_col = f"{p}_consensus"
        llm_col = f"{p}_score_llm"
        valid = wide[[cons_col, llm_col]].dropna()
        if len(valid) > 0:
            y_true = valid[cons_col].astype(int)
            y_pred = valid[llm_col].astype(int)
            prec, rec, f1, support = precision_recall_fscore_support(
                y_true, y_pred, labels=CLASSES, zero_division=0
            )
            cm = confusion_matrix(y_true, y_pred, labels=CLASSES).tolist()
            per_principle["llm_vs_consensus"] = {
                "n": int(len(valid)),
                "kappa": float(cohen_kappa_score(y_true, y_pred)),
                "weighted_kappa_linear": float(cohen_kappa_score(y_true, y_pred, weights="linear")),
                "raw_agreement": float(accuracy_score(y_true, y_pred)),
                "per_class": [
                    {
                        "class": c,
                        "precision": float(prec[i]),
                        "recall": float(rec[i]),
                        "f1": float(f1[i]),
                        "support": int(support[i]),
                    } for i, c in enumerate(CLASSES)
                ],
                "confusion_matrix": cm,
                "confusion_matrix_axes": {"rows": "consensus (truth)", "cols": "llm"},
            }

        # Provenance counts
        prov_col = f"{p}_provenance"
        if prov_col in wide.columns:
            per_principle["consensus_provenance"] = wide[prov_col].value_counts().to_dict()

        summary[p] = per_principle
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--round1", required=True, type=Path)
    parser.add_argument("--round2-rater-a", type=Path, default=None,
                        help="SQLite db from rater A round 2")
    parser.add_argument("--round2-rater-b", type=Path, default=None,
                        help="SQLite db from rater B round 2")
    parser.add_argument("--extreme", type=Path, default=None,
                        help="CSV of session-resolved extreme cases")
    parser.add_argument("--tiebreak", type=Path, default=None,
                        help="CSV of PI tiebreaks for residual disagreement")
    parser.add_argument("--sample", required=True, type=Path,
                        help="holdout_sample.csv (for LLM scores)")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--confusion", type=Path, default=None)
    parser.add_argument("--audit", type=Path, default=None,
                        help="Per-method final scores CSV (audit trail)")
    args = parser.parse_args()

    round1 = load_round1(args.round1)

    round2_by_rater = {
        "annotator_a": load_round2(args.round2_rater_a, "annotator_a") if args.round2_rater_a else pd.DataFrame(),
        "annotator_b": load_round2(args.round2_rater_b, "annotator_b") if args.round2_rater_b else pd.DataFrame(),
    }
    for r, df in round2_by_rater.items():
        print(f"  Round-2 entries for {r}: {len(df)}", file=sys.stderr)

    merged = merge_rounds(round1, round2_by_rater)
    wide = apply_resolutions(merged, args.extreme, args.tiebreak)

    sample = pd.read_csv(args.sample)
    summary = compute_agreement(wide, sample)

    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote final summary to {args.output}", file=sys.stderr)

    if args.confusion:
        rows = []
        for p, info in summary.items():
            cm = info.get("llm_vs_consensus", {}).get("confusion_matrix")
            if cm is None:
                continue
            for i, true_c in enumerate(CLASSES):
                for j, pred_c in enumerate(CLASSES):
                    rows.append({
                        "principle": p,
                        "consensus_class": true_c,
                        "llm_class": pred_c,
                        "count": cm[i][j],
                    })
        pd.DataFrame(rows).to_csv(args.confusion, index=False)
        print(f"Wrote confusion matrices to {args.confusion}", file=sys.stderr)

    if args.audit:
        wide.to_csv(args.audit, index=False)
        print(f"Wrote audit trail to {args.audit}", file=sys.stderr)


if __name__ == "__main__":
    main()