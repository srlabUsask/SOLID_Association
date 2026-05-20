"""
Multiple-comparison correction: Bonferroni vs. Benjamini-Hochberg FDR.

Applies both Bonferroni and BH-FDR corrections to the per-project
Mann-Whitney rank-biserial tests (8 projects x 3 principles = 24
comparisons). Reports significance under both, allowing direct
comparison of how the conclusions depend on the choice of correction.
"""
import pandas as pd
import numpy as np
from statsmodels.stats.multitest import multipletests

# Read per-project Mann-Whitney results
df = pd.read_csv("Results/rq1_analysis/per_project_method_comparison.csv")

# Restrict to the three principles
df = df[df["principle"].isin(["SRP", "OCP", "DIP"])].copy()
df = df.sort_values(["principle", "project"]).reset_index(drop=True)

n_tests = len(df)
alpha = 0.05

# Bonferroni (already applied in the paper as tiered)
bonf_threshold = alpha / n_tests
df["bonferroni_threshold"] = bonf_threshold
df["bonferroni_sig"] = df["p_value"] < bonf_threshold

# BH-FDR at q = 0.05
rejected_bh, p_adj_bh, _, _ = multipletests(
    df["p_value"].values, alpha=alpha, method="fdr_bh"
)
df["bh_q_value"] = p_adj_bh
df["bh_sig"] = rejected_bh

# Tier markers for paper
def tier_marker(p, n):
    if p < 0.05 / (1000 * n):
        return "***"
    elif p < 0.05 / (100 * n):
        return "**"
    elif p < 0.05 / n:
        return "*"
    else:
        return ""

df["bonf_tier"] = df["p_value"].apply(lambda p: tier_marker(p, n_tests))

# Report
print(f"Total comparisons: {n_tests}")
print(f"Bonferroni threshold (alpha={alpha}): p < {bonf_threshold:.4f}")
print()
print("Per-comparison breakdown:")
print(f"{'Project':<20} {'Principle':<5} {'r_rb':>8} {'p':>11} {'Bonf':>5} {'BH-q':>9} {'BH':>4}")
print("-" * 70)
for _, row in df.iterrows():
    print(f"{row['project']:<20} {row['principle']:<5} "
          f"{row['r_rb']:>+.4f} {row['p_value']:>11.2e} "
          f"{'YES' if row['bonferroni_sig'] else '-':>5} "
          f"{row['bh_q_value']:>9.2e} "
          f"{'YES' if row['bh_sig'] else '-':>4}")

print()
print("=== Summary ===")
n_bonf = df["bonferroni_sig"].sum()
n_bh = df["bh_sig"].sum()
n_both = ((df["bonferroni_sig"]) & (df["bh_sig"])).sum()
n_bh_only = ((df["bh_sig"]) & (~df["bonferroni_sig"])).sum()
n_bonf_only = ((df["bonferroni_sig"]) & (~df["bh_sig"])).sum()
print(f"Significant by Bonferroni only: {n_bonf}")
print(f"Significant by BH-FDR only:      {n_bh}")
print(f"Significant by both:             {n_both}")
print(f"BH-FDR adds beyond Bonferroni:   {n_bh_only}")
print(f"Bonferroni adds beyond BH-FDR:   {n_bonf_only}")

# What's added by BH-FDR?
if n_bh_only > 0:
    print("\nResults significant under BH-FDR but not Bonferroni:")
    for _, row in df[(df["bh_sig"]) & (~df["bonferroni_sig"])].iterrows():
        print(f"  {row['project']:<20} {row['principle']:<5} "
              f"r_rb = {row['r_rb']:+.4f}, p = {row['p_value']:.2e}, "
              f"q = {row['bh_q_value']:.2e}")

df.to_csv("Results/multiple_comparison_results.csv", index=False)
print(f"\nWrote: Results/multiple_comparison_results.csv")