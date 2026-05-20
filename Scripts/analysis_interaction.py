"""
Interaction-term analysis: SOLID x MethodLOC in pooled regression.

Tests whether the SOLID-clone associations vary systematically with
method size by adding SRP*LOC, OCP*LOC, DIP*LOC interaction terms
to the pooled regression. Significant interactions formally confirm
that the pooled SOLID effects are size-mediated rather than uniform
across method sizes.

Reports the main-effect model and the interaction-extended model
side by side, with a likelihood-ratio test comparing them.

"""
import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy import stats as sps

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

def zstd(x):
    return (x - x.mean()) / x.std()

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
        lambda r: int((r["project"], r["norm_path"], r["startline"]) in clone_keys),
        axis=1
    )
    methods = methods.drop_duplicates(subset=["project", "norm_path", "startline"])
    methods = methods.dropna(subset=["srp", "ocp", "dip", "method_loc"])
    print(f"Corpus: {len(methods)} methods, {methods['is_cloned'].sum()} cloned")

    # Standardise continuous predictors (pooled means/SDs)
    methods["SRP_z"] = zstd(methods["srp"])
    methods["OCP_z"] = zstd(methods["ocp"])
    methods["DIP_z"] = zstd(methods["dip"])
    methods["LOC_z"] = zstd(methods["method_loc"])

    # Project fixed effects (one-hot, drop one for baseline)
    project_dummies = pd.get_dummies(methods["project"], prefix="proj", drop_first=True).astype(int)
    base = pd.concat([
        methods[["SRP_z", "OCP_z", "DIP_z", "LOC_z"]].reset_index(drop=True),
        project_dummies.reset_index(drop=True),
    ], axis=1)
    y = methods["is_cloned"].reset_index(drop=True)

    # Model 1: main-effects only (baseline)
    X1 = sm.add_constant(base)
    m1 = sm.Logit(y, X1).fit(disp=0)

    # Model 2: with SOLID*LOC interactions
    base2 = base.copy()
    base2["SRP_x_LOC"] = base2["SRP_z"] * base2["LOC_z"]
    base2["OCP_x_LOC"] = base2["OCP_z"] * base2["LOC_z"]
    base2["DIP_x_LOC"] = base2["DIP_z"] * base2["LOC_z"]
    X2 = sm.add_constant(base2)
    m2 = sm.Logit(y, X2).fit(disp=0)

    # Likelihood ratio test
    lr_stat = 2 * (m2.llf - m1.llf)
    df = 3
    lr_p = sps.chi2.sf(lr_stat, df)

    print(f"\n=== Model 1: SOLID main effects only ===")
    print(f"  Pseudo R^2 = {m1.prsquared:.4f}, log-lik = {m1.llf:.2f}")
    for term in ["SRP_z", "OCP_z", "DIP_z", "LOC_z"]:
        coef = m1.params[term]
        or_ = np.exp(coef)
        lo, hi = m1.conf_int().loc[term].tolist()
        p = m1.pvalues[term]
        print(f"  {term:10s}  OR = {or_:.3f}  [{np.exp(lo):.3f}, {np.exp(hi):.3f}]  p = {p:.2e}")

    print(f"\n=== Model 2: SOLID main effects + SOLIDxLOC interactions ===")
    print(f"  Pseudo R^2 = {m2.prsquared:.4f}, log-lik = {m2.llf:.2f}")
    for term in ["SRP_z", "OCP_z", "DIP_z", "LOC_z",
                 "SRP_x_LOC", "OCP_x_LOC", "DIP_x_LOC"]:
        coef = m2.params[term]
        or_ = np.exp(coef)
        lo, hi = m2.conf_int().loc[term].tolist()
        p = m2.pvalues[term]
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
        print(f"  {term:12s}  OR = {or_:.3f}  [{np.exp(lo):.3f}, {np.exp(hi):.3f}]  p = {p:.2e}  {sig}")

    print(f"\n=== Likelihood ratio test (Model 2 vs Model 1) ===")
    print(f"  LR stat = {lr_stat:.2f}, df = {df}, p = {lr_p:.2e}")
    print(f"  Pseudo R^2 increase: {m2.prsquared - m1.prsquared:.4f}")

    # Save key statistics to CSV
    rows = []
    for term in ["SRP_z", "OCP_z", "DIP_z", "LOC_z"]:
        rows.append({
            "model": "main_effects", "term": term,
            "OR": np.exp(m1.params[term]),
            "OR_lo": np.exp(m1.conf_int().loc[term, 0]),
            "OR_hi": np.exp(m1.conf_int().loc[term, 1]),
            "p_value": m1.pvalues[term],
        })
    for term in ["SRP_z", "OCP_z", "DIP_z", "LOC_z",
                 "SRP_x_LOC", "OCP_x_LOC", "DIP_x_LOC"]:
        rows.append({
            "model": "with_interactions", "term": term,
            "OR": np.exp(m2.params[term]),
            "OR_lo": np.exp(m2.conf_int().loc[term, 0]),
            "OR_hi": np.exp(m2.conf_int().loc[term, 1]),
            "p_value": m2.pvalues[term],
        })
    rows.append({
        "model": "lr_test", "term": "model2_vs_model1",
        "OR": None, "OR_lo": None, "OR_hi": None,
        "p_value": lr_p,
    })
    pd.DataFrame(rows).to_csv("Results/interaction_results.csv", index=False)
    print(f"\nWrote: Results/interaction_results.csv")

if __name__ == "__main__":
    main()