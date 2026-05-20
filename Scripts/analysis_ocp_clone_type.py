"""
OCP-by-clone-type breakdown.

Computes mean SOLID scores and rank-biserial associations separately
for Type-1, Type-2, and Type-3 clones vs. non-cloned methods. Tests
whether the OCP-clone association differs by clone type.

The "OCP creates polymorphic families" hypothesis predicts stronger
OCP-clone associations for Type-2/Type-3 (parallel polymorphic
implementations differing in identifiers) than for Type-1 (textually
identical).

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

_TYPE_PRIORITY = {"T3": 3, "T2": 2, "T1": 1}

def normalise_path(p):
    if isinstance(p, str) and "/src/" in p:
        return p.split("/src/")[-1]
    return None

def compute_rrb(treated, control, principle):
    treated_vals = treated[principle].dropna()
    control_vals = control[principle].dropna()
    if len(treated_vals) < 10 or len(control_vals) < 10:
        return None, None, len(treated_vals), len(control_vals)
    u, p = stats.mannwhitneyu(treated_vals, control_vals, alternative="two-sided")
    n1, n2 = len(treated_vals), len(control_vals)
    r_rb = 1 - (2 * u) / (n1 * n2)
    return r_rb, p, n1, n2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method_csv", required=True)
    parser.add_argument("--clone_csv", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    methods = pd.read_csv(args.method_csv)
    methods["norm_path"] = methods["file_path"].apply(normalise_path)
    methods = methods[methods["norm_path"].notna()].copy()
    methods["method_loc"] = methods["endline"] - methods["startline"] + 1

    clones = pd.read_csv(args.clone_csv)
    clones["project_mapped"] = clones["project"].map(PROJECT_MAP)
    clones["norm_path"] = clones["file_path"]

    # Per method, determine the strongest clone type it participates in
    # using T3 > T2 > T1 priority (consistent with analysis_rq1.py)
    def strongest_type(types_str):
        types = set(types_str)
        for t in ["T3", "T2", "T1"]:
            if t in types:
                return t
        return None

    clones_by_method = clones.groupby(
        ["project_mapped", "norm_path", "startline"]
    )["clone_type"].apply(set).reset_index()
    clones_by_method["strongest_type"] = clones_by_method["clone_type"].apply(strongest_type)
    type_map = dict(zip(
        zip(clones_by_method["project_mapped"], clones_by_method["norm_path"], clones_by_method["startline"]),
        clones_by_method["strongest_type"]
    ))

    methods["clone_type"] = methods.apply(
        lambda r: type_map.get((r["project"], r["norm_path"], r["startline"]), None),
        axis=1
    )
    methods["is_cloned"] = methods["clone_type"].notna().astype(int)
    methods = methods.drop_duplicates(subset=["project", "norm_path", "startline"])

    print(f"Joined corpus: {len(methods)} methods, {methods['is_cloned'].sum()} cloned")
    print("\nClone-type distribution (deduplicated):")
    print(methods["clone_type"].value_counts(dropna=False).to_string())

    non_cloned = methods[methods["is_cloned"] == 0]

    rows = []
    print("\n=== PER-CLONE-TYPE ANALYSIS (vs non-cloned baseline) ===\n")
    for clone_type in ["T1", "T2", "T3"]:
        cloned_t = methods[methods["clone_type"] == clone_type]
        n = len(cloned_t)
        if n < 10:
            print(f"{clone_type}: n = {n} — too few for inferential analysis")
            for p in ["srp", "ocp", "dip"]:
                rows.append({
                    "clone_type": clone_type, "principle": p.upper(),
                    "n_cloned": n, "n_non_cloned": len(non_cloned),
                    "mean_cloned": cloned_t[p].mean() if n > 0 else None,
                    "mean_non_cloned": non_cloned[p].mean(),
                    "r_rb": None, "p_value": None,
                })
            continue
        print(f"{clone_type}: n = {n}")
        for p in ["srp", "ocp", "dip"]:
            r_rb, pv, nc, nnc = compute_rrb(cloned_t, non_cloned, p)
            mean_c = cloned_t[p].mean()
            mean_nc = non_cloned[p].mean()
            print(f"  {p.upper()}: mean_cloned={mean_c:.3f}, mean_non_cloned={mean_nc:.3f}, "
                  f"r_rb={r_rb:+.4f}, p={pv:.2e}")
            rows.append({
                "clone_type": clone_type, "principle": p.upper(),
                "n_cloned": nc, "n_non_cloned": nnc,
                "mean_cloned": mean_c, "mean_non_cloned": mean_nc,
                "r_rb": r_rb, "p_value": pv,
            })

    pd.DataFrame(rows).to_csv(
        os.path.join(args.output_dir, "ocp_clone_type_results.csv"), index=False
    )
    print(f"\nWrote results to: {args.output_dir}/ocp_clone_type_results.csv")

if __name__ == "__main__":
    main()