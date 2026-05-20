"""
analyze_round3_dip.py

Round-3 DIP-only analysis. Uses round-3 annotation databases for the DIP
column only, leaving SRP and OCP results from the round-1+round-2 analysis
unchanged. Produces inter-rater and LLM-vs-consensus kappa for DIP, plus
provenance counts for the new DIP consensus.

Inputs:
    --round3-rater-a: SQLite db from rater A round 3
    --round3-rater-b: SQLite db from rater B round 3
    --sample: holdout_sample.csv (for LLM DIP scores)
    --extreme: extreme_resolutions.csv (PI-resolved DIP cases from calibration session)
    --tiebreak (optional): tiebreak.csv if PI tiebreak is applied

Output:
    --output: final_dip_round3_summary.json
    --audit: per_method_dip_round3.csv

Usage:
    python analyze_round3_dip.py \
        --round3-rater-a round3_rater_a.db \
        --round3-rater-b round3_rater_b.db \
        --sample ../holdout_sample.csv \
        --extreme ../extreme_resolutions.csv \
        --output ../final_dip_round3_summary.json \
        --audit ../per_method_dip_round3.csv
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


CLASSES = [0, 1, 2]


def load_round3(db_path: Path, rater_label: str) -> pd.DataFrame:
    """Load round-3 DIP annotations only."""
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT method_id, dip_score, dip_na FROM annotations", conn)
    if df.empty:
        return df
    df["method_id"] = df["method_id"].astype(str)
    df["rater"] = rater_label
    return df


def apply_resolutions(wide: pd.DataFrame, extreme_path: Path | None,
                      tiebreak_path: Path | None) -> pd.DataFrame:
    """
    Build DIP consensus.

    Priority order:
        1. PI tiebreak entry, if present
        2. Calibration session resolution, if present
        3. Both raters agree post-round-3: that value
        4. Both raters disagree post-round-3: NaN, flagged 'unresolved'
    """
    extreme_lookup = {}
    if extreme_path and extreme_path.exists():
        extreme = pd.read_csv(extreme_path)
        for _, row in extreme.iterrows():
            if row["principle"].lower() == "dip":
                try:
                    extreme_lookup[str(row["method_id"])] = int(row["agreed_score"])
                except (ValueError, TypeError):
                    pass

    tiebreak_lookup = {}
    if tiebreak_path and tiebreak_path.exists():
        tiebreak = pd.read_csv(tiebreak_path)
        col = "tiebreak_score" if "tiebreak_score" in tiebreak.columns else "agreed_score"
        for _, row in tiebreak.iterrows():
            if row["principle"].lower() == "dip":
                tiebreak_lookup[str(row["method_id"])] = int(row[col])

    consensus = []
    provenance = []
    for _, row in wide.iterrows():
        mid = row["method_id"]

        if mid in tiebreak_lookup:
            consensus.append(tiebreak_lookup[mid])
            provenance.append("tiebreak")
            continue

        if mid in extreme_lookup:
            consensus.append(extreme_lookup[mid])
            provenance.append("session")
            continue

        sa = row.get("dip_annotator_a")
        sb = row.get("dip_annotator_b")
        na_a = row.get("dip_na_annotator_a", 0) or 0
        na_b = row.get("dip_na_annotator_b", 0) or 0

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

    wide["dip_consensus"] = consensus
    wide["dip_provenance"] = provenance
    return wide


def compute(wide: pd.DataFrame, sample: pd.DataFrame) -> dict:
    summary = {}

    # Inter-rater
    valid_pair = wide[["dip_annotator_a", "dip_annotator_b"]].dropna()
    if len(valid_pair) > 0:
        ya = valid_pair["dip_annotator_a"].astype(int)
        yb = valid_pair["dip_annotator_b"].astype(int)
        summary["inter_rater_round3"] = {
            "n": int(len(valid_pair)),
            "kappa": float(cohen_kappa_score(ya, yb)),
            "weighted_kappa_linear": float(cohen_kappa_score(ya, yb, weights="linear")),
            "raw_agreement": float(accuracy_score(ya, yb)),
        }

    # LLM vs consensus
    llm = sample[["method_id", "dip_score_llm"]].copy()
    llm["method_id"] = llm["method_id"].astype(str)
    wide = wide.merge(llm, on="method_id", how="left")

    valid = wide[["dip_consensus", "dip_score_llm"]].dropna()
    if len(valid) > 0:
        y_true = valid["dip_consensus"].astype(int)
        y_pred = valid["dip_score_llm"].astype(int)
        prec, rec, f1, support = precision_recall_fscore_support(
            y_true, y_pred, labels=CLASSES, zero_division=0
        )
        cm = confusion_matrix(y_true, y_pred, labels=CLASSES).tolist()
        summary["llm_vs_consensus"] = {
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

    summary["consensus_provenance"] = wide["dip_provenance"].value_counts().to_dict()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--round3-rater-a", required=True, type=Path)
    parser.add_argument("--round3-rater-b", required=True, type=Path)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--extreme", type=Path, default=None)
    parser.add_argument("--tiebreak", type=Path, default=None)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", type=Path, default=None)
    args = parser.parse_args()

    a = load_round3(args.round3_rater_a, "annotator_a")
    b = load_round3(args.round3_rater_b, "annotator_b")

    if a.empty or b.empty:
        sys.exit("ERROR: one or both round-3 databases are empty.")

    a = a.rename(columns={"dip_score": "dip_annotator_a", "dip_na": "dip_na_annotator_a"}).drop(columns="rater")
    b = b.rename(columns={"dip_score": "dip_annotator_b", "dip_na": "dip_na_annotator_b"}).drop(columns="rater")

    wide = a.merge(b, on="method_id", how="outer")
    print(f"  Round-3 entries: a={len(a)}, b={len(b)}, merged={len(wide)}",
          file=sys.stderr)

    wide = apply_resolutions(wide, args.extreme, args.tiebreak)

    sample = pd.read_csv(args.sample)
    summary = compute(wide, sample)

    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote summary to {args.output}", file=sys.stderr)

    if args.audit:
        wide.to_csv(args.audit, index=False)
        print(f"Wrote audit trail to {args.audit}", file=sys.stderr)


if __name__ == "__main__":
    main()