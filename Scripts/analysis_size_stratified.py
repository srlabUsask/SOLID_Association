"""
Size-stratified rank-biserial analysis for RQ1.

Bins methods into method-LOC quartiles, then computes
Mann-Whitney/rank-biserial for SRP, OCP, and DIP within each bin.
This isolates whether observed pooled associations are confounded
by method size.


"""

import os
import argparse
import pandas as pd
import numpy as np
from scipy import stats

PROJECT_MAP = {
    "commonslang": "commonslang_SOLID_Eval",
    "fitnesse": "fitnesse_SOLID_Eval",
    "hibernate-orm": "hibernate-orm_SOLID_Eval",
    "jackson-databind_": "jackson-databind__SOLID_Eval",
    "jmeter": "jmeter_SOLID_Eval",
    "junit5": "junit5_SOLID_Eval",
    "selenium-trunk": "selenium-trunk_SOLID_Eval",
    "struts": "struts_SOLID_Eval",
}

def normalise_path(p):
    if isinstance(p, str) and "/src/" in p:
        return p.split("/src/")[-1]
    return None

def compute_rrb(df, principle):
    cloned = df[df["is_cloned"] == 1][principle].dropna()
    non_cloned = df[df["is_cloned"] == 0][principle].dropna()
    if len(cloned) < 10 or len(non_cloned) < 10:
        return None, None, None, len(cloned), len(non_cloned)
    u, p = stats.mannwhitneyu(cloned, non_cloned, alternative="two-sided")
    n1, n2 = len(cloned), len(non_cloned)
    r_rb = 1 - (2 * u) / (n1 * n2)
    return u, p, r_rb, n1, n2

def main():
    parser = argparse.ArgumentParser(
        description="Size-stratified rank-biserial analysis"
    )
    parser.add_argument("--method_csv", required=True)
    parser.add_argument("--clone_csv", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load methods, normalize path, compute LOC
    methods = pd.read_csv(args.method_csv)
    methods["norm_path"] = methods["file_path"].apply(normalise_path)
    methods = methods[methods["norm_path"].notna()].copy()
    methods["method_loc"] = methods["endline"] - methods["startline"] + 1

    # Load clones, use file_path directly (already post-/src/)
    clones = pd.read_csv(args.clone_csv)
    clones["project_mapped"] = clones["project"].map(PROJECT_MAP)
    clones["norm_path"] = clones["file_path"]
    clone_keys = set(zip(clones["project_mapped"], clones["norm_path"], clones["startline"]))

    methods["is_cloned"] = methods.apply(
        lambda r: 1 if (r["project"], r["norm_path"], r["startline"]) in clone_keys else 0,
        axis=1,
    )
    methods = methods.drop_duplicates(subset=["project", "norm_path", "startline"])

    print(f"Joined corpus: {len(methods)} methods, {methods['is_cloned'].sum()} cloned")

    quartiles = methods["method_loc"].quantile([0.25, 0.5, 0.75]).values
    print(f"Quartile cutoffs (LOC): {quartiles}")

    def bucket(loc):
        if loc <= quartiles[0]: return "Q1 (tiny)"
        if loc <= quartiles[1]: return "Q2 (small)"
        if loc <= quartiles[2]: return "Q3 (medium)"
        return "Q4 (large)"

    methods["size_bucket"] = methods["method_loc"].apply(bucket)

    rows = []
    print("\n=== SIZE-STRATIFIED ANALYSIS ===")
    for bucket_name in ["Q1 (tiny)", "Q2 (small)", "Q3 (medium)", "Q4 (large)"]:
        df_b = methods[methods["size_bucket"] == bucket_name]
        n_total = len(df_b)
        n_cloned = df_b["is_cloned"].sum()
        print(f"\n{bucket_name}: n = {n_total}, cloned = {n_cloned} ({n_cloned/n_total*100:.1f}%)")
        for p in ["srp", "ocp", "dip"]:
            u, pv, rrb, nc, nnc = compute_rrb(df_b, p)
            if rrb is None:
                print(f"  {p.upper()}: insufficient data (n_cloned={nc}, n_non_cloned={nnc})")
                rows.append({
                    "size_bucket": bucket_name, "principle": p.upper(),
                    "n_cloned": nc, "n_non_cloned": nnc,
                    "r_rb": None, "p_value": None,
                    "loc_min": (quartiles[0]+1 if bucket_name == "Q2 (small)" else None),
                })
            else:
                print(f"  {p.upper()}: r_rb = {rrb:+.4f}, p = {pv:.2e}, n = ({nc}, {nnc})")
                rows.append({
                    "size_bucket": bucket_name, "principle": p.upper(),
                    "n_cloned": nc, "n_non_cloned": nnc,
                    "r_rb": rrb, "p_value": pv,
                })

    pd.DataFrame(rows).to_csv(
        os.path.join(args.output_dir, "size_stratified_results.csv"), index=False
    )

    # Also save the methods dataframe with the size_bucket column for downstream use
    methods[["project", "norm_path", "startline", "endline", "method_loc",
             "size_bucket", "srp", "ocp", "dip", "is_cloned"]].to_csv(
        os.path.join(args.output_dir, "methods_with_size_bucket.csv"), index=False
    )

    print(f"\nWrote size-stratified results to: {args.output_dir}/size_stratified_results.csv")
    print(f"Wrote methods+buckets to:           {args.output_dir}/methods_with_size_bucket.csv")

if __name__ == "__main__":
    main()