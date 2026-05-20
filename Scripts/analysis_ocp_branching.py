"""
OCP-by-branching stratification.

Tests whether the OCP wrong-direction effect (cloned methods having
HIGHER OCP scores than non-cloned methods) is driven by short methods
with no branching, which auto-score high on OCP under our rubric
because they lack any conditional logic to branch on.

Stratifies the NiCad-eligible corpus (LOC >= 10) into methods that
contain branching constructs (if/else/switch) vs. methods that don't,
and re-reports the OCP-clone association within each stratum.

Hypothesis: if the wrong-direction effect persists in the "has-branching"
subset, it reflects genuine construct overlap between OCP-compliant
design and textual clone detection. If it disappears, it confirms
the trivial-OCP-compliance artifact.

"""
import pandas as pd
import numpy as np
import re
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

# Match Java conditional keywords as whole words.
# Excludes "if" appearing inside identifiers (e.g., "modifier", "specifier").
BRANCH_REGEX = re.compile(r"\b(if|else|switch|case)\b")

def normalise_path(p):
    if isinstance(p, str) and "/src/" in p:
        return p.split("/src/")[-1]
    return None

def has_branching(method_body):
    if not isinstance(method_body, str):
        return False
    return bool(BRANCH_REGEX.search(method_body))

def rrb(treated, control, principle):
    t = treated[principle].dropna()
    c = control[principle].dropna()
    if len(t) < 10 or len(c) < 10:
        return None, None, len(t), len(c)
    u, p = stats.mannwhitneyu(t, c, alternative="two-sided")
    r = 1 - (2 * u) / (len(t) * len(c))
    return r, p, len(t), len(c)

def report_subset(name, eligible, principle="ocp"):
    cloned = eligible[eligible["is_cloned"] == 1]
    non_cloned = eligible[eligible["is_cloned"] == 0]
    r, p, n_t, n_c = rrb(cloned, non_cloned, principle)
    mean_c = cloned[principle].mean()
    mean_n = non_cloned[principle].mean()
    print(f"  {name}:")
    print(f"    n_total = {len(eligible)}, n_cloned = {n_t}, n_non_cloned = {n_c}")
    print(f"    mean_cloned = {mean_c:.3f}, mean_non_cloned = {mean_n:.3f}")
    if r is not None:
        print(f"    r_rb = {r:+.4f}, p = {p:.2e}")
    else:
        print(f"    insufficient sample for r_rb")
    return {
        "subset": name, "principle": principle.upper(),
        "n_total": len(eligible), "n_cloned": n_t, "n_non_cloned": n_c,
        "mean_cloned": mean_c, "mean_non_cloned": mean_n,
        "r_rb": r, "p_value": p,
    }

def main():
    methods = pd.read_csv("Results/per_method_scores.csv")
    methods["norm_path"] = methods["file_path"].apply(normalise_path)
    methods = methods[methods["norm_path"].notna()].copy()
    methods["method_loc"] = methods["endline"] - methods["startline"] + 1

    # Determine the source column for the method body.
    # Try common column names; fall back to first text-looking column.
    body_col = None
    for c in ["method_body", "body", "source", "code", "method_text"]:
        if c in methods.columns:
            body_col = c
            break
    if body_col is None:
        print("Columns available:", list(methods.columns))
        raise ValueError("Could not find a method-body column. "
                         "Edit body_col selection above.")
    print(f"Using method-body column: '{body_col}'")

    methods["has_branching"] = methods[body_col].apply(has_branching)

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

    # Restrict to NiCad-eligible subset
    eligible = methods[methods["method_loc"] >= 10].copy()
    print(f"\nNiCad-eligible (LOC >= 10): {len(eligible)} methods")
    print(f"  with branching:    {eligible['has_branching'].sum()}")
    print(f"  without branching: {(~eligible['has_branching']).sum()}")

    rows = []
    print(f"\n=== OCP-by-branching within NiCad-eligible subset ===")
    rows.append(report_subset("nicad_eligible_all", eligible, "ocp"))
    rows.append(report_subset("nicad_eligible_has_branching",
                              eligible[eligible["has_branching"]], "ocp"))
    rows.append(report_subset("nicad_eligible_no_branching",
                              eligible[~eligible["has_branching"]], "ocp"))

    # For comparison, do the same for SRP and DIP
    for principle in ["srp", "dip"]:
        print(f"\n=== {principle.upper()}-by-branching within NiCad-eligible subset ===")
        rows.append(report_subset("nicad_eligible_all", eligible, principle))
        rows.append(report_subset("nicad_eligible_has_branching",
                                  eligible[eligible["has_branching"]], principle))
        rows.append(report_subset("nicad_eligible_no_branching",
                                  eligible[~eligible["has_branching"]], principle))

    pd.DataFrame(rows).to_csv("Results/ocp_branching_results.csv", index=False)
    print(f"\nWrote: Results/ocp_branching_results.csv")

if __name__ == "__main__":
    main()