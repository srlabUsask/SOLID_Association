"""
analysis_bootstrap_ci.py

Bootstrap 95% confidence intervals for pooled rank-biserial correlations
(SRP, OCP, DIP) at the pooled level and within MethodLOC quartiles.

Uses 1,000 bootstrap resamples with stratified sampling by clone status
to preserve class proportions.
"""

import argparse
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu


def rank_biserial(x_cloned, x_noncloned):
    """Rank-biserial correlation from Mann-Whitney U."""
    n1, n2 = len(x_cloned), len(x_noncloned)
    if n1 == 0 or n2 == 0:
        return np.nan
    U, _ = mannwhitneyu(x_cloned, x_noncloned, alternative="two-sided")
    # r_rb sign convention: positive => cloned ranks lower (worse compliance)
    r_rb = 1 - (2 * U) / (n1 * n2)
    return r_rb


def bootstrap_ci(df, principle_col, clone_col, n_boot=1000, seed=42, alpha=0.05):
    """Stratified bootstrap CI for rank-biserial."""
    rng = np.random.default_rng(seed)
    cloned = df[df[clone_col] == 1][principle_col].values
    noncloned = df[df[clone_col] == 0][principle_col].values
    n1, n2 = len(cloned), len(noncloned)

    if n1 == 0 or n2 == 0:
        return np.nan, np.nan, np.nan

    point = rank_biserial(cloned, noncloned)
    boots = []
    for _ in range(n_boot):
        c_idx = rng.integers(0, n1, n1)
        nc_idx = rng.integers(0, n2, n2)
        boots.append(rank_biserial(cloned[c_idx], noncloned[nc_idx]))

    lo = np.percentile(boots, 100 * alpha / 2)
    hi = np.percentile(boots, 100 * (1 - alpha / 2))
    return point, lo, hi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True,
                        help="Merged corpus with SOLID scores + is_cloned + method_loc")
    parser.add_argument("--n_boot", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="Results/bootstrap_ci.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    print(f"Loaded {len(df):,} methods")

    # Drop missing
    needed = ["srp", "ocp", "dip", "is_cloned", "method_loc"]
    df = df.dropna(subset=needed)
    print(f"After dropna: {len(df):,}")

    # Define quartile bins (matching size_stratified analysis)
    df["q"] = pd.cut(df["method_loc"],
                     bins=[0, 3, 5, 9, df["method_loc"].max()],
                     labels=["Q1 (1-3)", "Q2 (4-5)", "Q3 (6-9)", "Q4 (>=10)"],
                     include_lowest=True)

    rows = []
    for principle in ["srp", "ocp", "dip"]:
        # Pooled
        p, lo, hi = bootstrap_ci(df, principle, "is_cloned",
                                  n_boot=args.n_boot, seed=args.seed)
        rows.append({"scope": "POOLED", "principle": principle.upper(),
                     "n": len(df), "r_rb": p, "ci_lo": lo, "ci_hi": hi})
        # Per quartile
        for q in df["q"].cat.categories:
            sub = df[df["q"] == q]
            p, lo, hi = bootstrap_ci(sub, principle, "is_cloned",
                                      n_boot=args.n_boot, seed=args.seed)
            rows.append({"scope": q, "principle": principle.upper(),
                         "n": len(sub), "r_rb": p, "ci_lo": lo, "ci_hi": hi})

    out = pd.DataFrame(rows)
    print("\nBootstrap 95% CIs (n_boot = {}):".format(args.n_boot))
    print(out.to_string(index=False, float_format=lambda x: f"{x:+.3f}"
                        if isinstance(x, float) else str(x)))
    out.to_csv(args.output, index=False)
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()