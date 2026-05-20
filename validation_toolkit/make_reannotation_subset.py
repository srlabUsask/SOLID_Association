"""
make_reannotation_subset.py
---------------------------
Generates a subset of holdout_sample.csv containing only the methods
that need re-annotation in round 2 (those with adjacent-class
disagreements: 0↔1 or 1↔2 between the two raters).

Methods with extreme disagreements (0↔2) are NOT included here; those
are resolved face-to-face in the calibration session worksheet.

The output CSV has the same schema as holdout_sample.csv so the existing
annotate.py runs on it without any changes.

Inputs:
    - disagreements_to_resolve.csv (full disagreement list)
    - holdout_sample.csv (source of truth for method content + LLM scores)

Output:
    - reannotation_round2.csv

Usage:
    python make_reannotation_subset.py \\
        --disagreements ../disagreements_to_resolve.csv \\
        --sample ../holdout_sample.csv \\
        --output ../reannotation_round2.csv
"""

import argparse
import json
from pathlib import Path

import pandas as pd


def is_adjacent(rater_scores_json: str) -> bool:
    """Return True if the two rater scores differ by exactly 1."""
    try:
        d = json.loads(rater_scores_json)
    except (TypeError, ValueError):
        return False
    vals = sorted([int(v) for v in d.values() if v is not None])
    if len(vals) < 2:
        return False
    return abs(vals[0] - vals[1]) == 1


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--disagreements", required=True, type=Path)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    dis = pd.read_csv(args.disagreements)
    dis = dis[dis["reason"] == "disagreement_no_tiebreak"].copy()
    dis["adjacent"] = dis["rater_scores"].apply(is_adjacent)
    adjacent = dis[dis["adjacent"]].copy()

    print(f"Adjacent disagreements: {len(adjacent)} across "
          f"{adjacent['method_id'].nunique()} unique methods")
    print("By principle:")
    print(adjacent["principle"].value_counts().to_string())

    # Take the union of method IDs that have any adjacent disagreement.
    # A single method might have adjacent disagreements on multiple
    # principles; we re-annotate the whole method either way (the app
    # asks for all three principles per method).
    method_ids = sorted(adjacent["method_id"].astype(str).unique())
    print(f"\nUnique methods to re-annotate: {len(method_ids)}")

    sample = pd.read_csv(args.sample)
    sample["method_id"] = sample["method_id"].astype(str)
    subset = sample[sample["method_id"].isin(method_ids)].copy()

    if len(subset) != len(method_ids):
        missing = set(method_ids) - set(subset["method_id"])
        print(f"WARNING: {len(missing)} method IDs from disagreements not "
              f"found in sample. First few: {list(missing)[:3]}")

    subset.to_csv(args.output, index=False)
    print(f"\nWrote {len(subset)} methods to {args.output}")
    print("\nUse this CSV with the existing annotate.py:")
    print(f"  python annotate.py --sample {args.output.name} "
          f"--db round2_<rater>.db --rubric rubric.html")


if __name__ == "__main__":
    main()