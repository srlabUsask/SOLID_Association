"""
NiCad-eligible subset analysis.

NiCad was configured with minsize=10, meaning methods of fewer than
~10 lines are effectively excluded from clone detection. This script
restricts the analysis to LOC >= 10 methods and re-reports pooled
rank-biserial associations for SRP/OCP/DIP.

This responds to a methodological constraint: short methods cannot
meaningfully participate in NiCad clones, so the pooled effect
inadvertently averages across an "eligible" and "ineligible" subset.

"""
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

def rrb(treated, control, principle):
    t = treated[principle].dropna()
    c = control[principle].dropna()
    if len(t) < 10 or len(c) < 10:
        return None, None, len(t), len(c)
    u, p = stats.mannwhitneyu(t, c, alternative="two-sided")
    r = 1 - (2 * u) / (len(t) * len(c))
    return r, p, len(t), len(c)

def main():
    methods = pd.read_csv("Results/per_method_scores.csv")
    methods["norm_path"] = methods["file_path"].apply(normalise_path)
    methods = methods[methods["norm_path"].notna()].copy()
    methods["method_loc"] = methods["endline"] - methods["startline"] + 1

    clones = pd.read_csv("Results/ALL_PROJECTS_clone_methods.csv")
    clones["project_mapped"] = clones["project"].map(PROJECT_MAP)
    clones["norm_path"] = clones["file_path"]
    clone_keys = set(zip(
        clones["project_mapped"], clones["norm_path"], clones["startline"]
    ))

    methods["is_cloned"] = methods.apply(
        lambda r: (r["project"], r["norm_path"], r["startline"]) in clone_keys,
        axis=1
    ).astype(int)
    methods = methods.drop_duplicates(subset=["project", "norm_path", "startline"])

    print(f"Full corpus: {len(methods)} methods, "
          f"{methods['is_cloned'].sum()} cloned "
          f"({methods['is_cloned'].mean() * 100:.1f}%)")

    # NiCad-eligible: methods with LOC >= 10 (configured minsize)
    eligible = methods[methods["method_loc"] >= 10].copy()
    print(f"\nNiCad-eligible (LOC >= 10): {len(eligible)} methods, "
          f"{eligible['is_cloned'].sum()} cloned "
          f"({eligible['is_cloned'].mean() * 100:.1f}%)")
    print(f"NiCad-ineligible (LOC < 10): {len(methods) - len(eligible)} methods, "
          f"{(methods['is_cloned'].sum() - eligible['is_cloned'].sum())} cloned")

    cloned = eligible[eligible["is_cloned"] == 1]
    non_cloned = eligible[eligible["is_cloned"] == 0]

    print(f"\n=== NiCad-eligible pooled rank-biserial (LOC >= 10) ===")
    rows = []
    for p in ["srp", "ocp", "dip"]:
        r, pv, n_t, n_c = rrb(cloned, non_cloned, p)
        mean_c = cloned[p].mean()
        mean_n = non_cloned[p].mean()
        print(f"  {p.upper()}: r_rb = {r:+.4f}, p = {pv:.2e}, "
              f"mean_cloned={mean_c:.3f}, mean_non_cloned={mean_n:.3f}, "
              f"n_cloned={n_t}, n_non_cloned={n_c}")
        rows.append({
            "subset": "nicad_eligible_LOC>=10",
            "principle": p.upper(),
            "r_rb": r, "p_value": pv,
            "mean_cloned": mean_c, "mean_non_cloned": mean_n,
            "n_cloned": n_t, "n_non_cloned": n_c,
        })

    print(f"\n=== Full-corpus comparison (for reference) ===")
    cloned_full = methods[methods["is_cloned"] == 1]
    non_cloned_full = methods[methods["is_cloned"] == 0]
    for p in ["srp", "ocp", "dip"]:
        r, pv, n_t, n_c = rrb(cloned_full, non_cloned_full, p)
        print(f"  {p.upper()}: r_rb = {r:+.4f}, p = {pv:.2e}")
        rows.append({
            "subset": "full_corpus",
            "principle": p.upper(),
            "r_rb": r, "p_value": pv,
            "mean_cloned": cloned_full[p].mean(),
            "mean_non_cloned": non_cloned_full[p].mean(),
            "n_cloned": n_t, "n_non_cloned": n_c,
        })

    pd.DataFrame(rows).to_csv("Results/nicad_eligible_results.csv", index=False)
    print(f"\nWrote: Results/nicad_eligible_results.csv")

if __name__ == "__main__":
    main()