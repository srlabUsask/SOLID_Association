import os
import argparse
import pandas as pd
import numpy as np
from scipy import stats

try:
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor
except ImportError:
    raise ImportError(
        "pip install statsmodels --break-system-packages"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Project name map: clone CSV project name → method CSV project name
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_MAP = {
    "commonslang"       : "commonslang_SOLID_Eval",
    "fitnesse"          : "fitnesse_SOLID_Eval",
    "hibernate-orm"     : "hibernate-orm_SOLID_Eval",
    "jackson-databind_" : "jackson-databind__SOLID_Eval",
    "jmeter"            : "jmeter_SOLID_Eval",
    "junit5"            : "junit5_SOLID_Eval",
    "selenium-trunk"    : "selenium-trunk_SOLID_Eval",
    "struts"            : "struts_SOLID_Eval",
}


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def normalise_path(p):
    """
    Extract the post-/src/ path segment — the stable join key between
    NiCad output paths and TXL-extracted method paths.
    """
    if isinstance(p, str) and "/src/" in p:
        return p.split("/src/")[-1]
    return os.path.basename(str(p)) if isinstance(p, str) else str(p)


def get_clone_project(clone_csv):
    df = pd.read_csv(clone_csv, nrows=1)
    return df["project"].iloc[0] if "project" in df.columns else None


# ─────────────────────────────────────────────────────────────────────────────
# Data merge
# ─────────────────────────────────────────────────────────────────────────────

def merge_solid_and_clones(method_csv, clone_csv):
    methods = pd.read_csv(method_csv)
    clones  = pd.read_csv(clone_csv)

    # ── Project filtering ──────────────────────────────────────────────────
    clone_project  = get_clone_project(clone_csv)
    method_project = PROJECT_MAP.get(clone_project, clone_project)
    methods        = methods[methods["project"] == method_project].copy()

    if len(methods) == 0:
        avail = pd.read_csv(method_csv)["project"].unique().tolist()
        raise ValueError(
            f"No methods found for project '{method_project}'.\n"
            f"Available: {avail}\nCheck PROJECT_MAP."
        )

    # ── Path normalisation ─────────────────────────────────────────────────
    methods = methods[
        methods["file_path"].astype(str).str.contains("/src/", na=False)
    ].copy()
    methods["file_path"] = methods["file_path"].astype(str).str.strip().apply(normalise_path)
    methods["startline"] = methods["startline"].astype(int)

    # Use file_path_raw for NiCad paths (preserves original path before any
    # normalisation artifacts from the XML parser)
    raw_col = "file_path_raw" if "file_path_raw" in clones.columns else "file_path"
    clones = clones[
        clones[raw_col].astype(str).str.contains("/src/", na=False)
    ].copy()
    clones["norm_path"] = clones[raw_col].astype(str).apply(normalise_path)
    clones["startline"] = clones["startline"].astype(int)

    # ── MethodLOC ─────────────────────────────────────────────────────────
    if "endline" in methods.columns:
        methods["method_loc"] = (
            methods["endline"].astype(float) - methods["startline"].astype(float) + 1
        ).clip(lower=1)
    else:
        methods["method_loc"] = 1.0
        print("  [WARN] No 'endline' column — method_loc = 1 (size control inactive).")

    # ── Merge ─────────────────────────────────────────────────────────────
    clone_cols = ["norm_path", "startline", "is_cloned"]
    if "clone_type" in clones.columns:
        clone_cols.append("clone_type")

    merged = methods.merge(
        clones[clone_cols],
        left_on=["file_path", "startline"],
        right_on=["norm_path", "startline"],
        how="left",
    )
    merged["is_cloned"] = merged["is_cloned"].fillna(0).astype(int)
    if "clone_type" in merged.columns:
        merged["clone_type"] = merged["clone_type"].fillna("none")

    n, nc = len(merged), merged["is_cloned"].sum()
    print(f"\n  Project        : {clone_project} → {method_project}")
    print(f"  Methods        : {n:,}  |  Cloned: {nc:,} ({nc/n*100:.1f}%)  |  Non-cloned: {n-nc:,}")
    print(f"  MethodLOC      : mean={merged['method_loc'].mean():.1f}  "
          f"median={merged['method_loc'].median():.0f}  "
          f"max={merged['method_loc'].max():.0f}\n")
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# VIF + correlation (saved to replication package; not tabled in paper)
# ─────────────────────────────────────────────────────────────────────────────

def compute_diagnostics(df, output_dir, label="overall"):
    predictors = [c for c in ["srp", "ocp", "dip", "method_loc"] if c in df.columns]
    subset     = df[predictors].dropna()

    corr = subset.corr(method="pearson").round(3)
    corr.to_csv(os.path.join(output_dir, f"correlation_matrix_{label}.csv"))

    X_raw    = sm.add_constant(subset)
    vif_rows = []
    for i, col in enumerate(X_raw.columns):
        if col == "const":
            continue
        v = variance_inflation_factor(X_raw.values, i)
        vif_rows.append({"predictor": col.upper(), "VIF": round(float(v), 3),
                         "flag": "HIGH>5" if v > 5 else ("MOD 2-5" if v > 2 else "OK<2")})

    vif_df = pd.DataFrame(vif_rows)
    vif_df.to_csv(os.path.join(output_dir, f"vif_{label}.csv"), index=False)

    print(f"\n── Correlation ({label}) ─────────────────────────────────────────")
    print(corr.to_string())
    print(f"\n── VIF ({label}) ─────────────────────────────────────────────────")
    print(vif_df.to_string(index=False))
    print("  Threshold: >5 concern; >10 severe.\n")
    return corr, vif_df


# ─────────────────────────────────────────────────────────────────────────────
# PRIMARY ANALYSIS: Mann-Whitney U
# ─────────────────────────────────────────────────────────────────────────────

def run_mann_whitney(df, output_dir):
    results    = []
    principles = ["srp", "ocp", "dip"]
    ctypes     = ["overall"]
    if "clone_type" in df.columns:
        ctypes += [t for t in df["clone_type"].unique() if t != "none"]

    for ctype in ctypes:
        sub        = df if ctype == "overall" else \
                     df[(df["clone_type"] == ctype) | (df["is_cloned"] == 0)]
        cloned     = sub[sub["is_cloned"] == 1]
        non_cloned = sub[sub["is_cloned"] == 0]

        for p in principles:
            c_vals  = cloned[p].dropna()
            nc_vals = non_cloned[p].dropna()
            u, pv = stats.mannwhitneyu(c_vals, nc_vals, alternative="two-sided")
            n1, n2 = len(c_vals), len(nc_vals)
            results.append({
                "clone_type"      : ctype,
                "principle"       : p.upper(),
                "n_cloned"        : n1,
                "n_non_cloned"    : n2,
                "mean_cloned"     : round(cloned[p].mean(), 4),
                "mean_non_cloned" : round(non_cloned[p].mean(), 4),
                "U_statistic"     : round(u, 2),
                "p_value"         : round(pv, 4),
                "rank_biserial_r" : round(1 - (2 * u) / (n1 * n2), 4),
                "significant_05"  : "Yes" if pv < 0.05 else "No",
            })

    mw_df = pd.DataFrame(results)
    mw_df.to_csv(os.path.join(output_dir, "mann_whitney_results.csv"), index=False)

    print("\n── Mann-Whitney Results (overall) ───────────────────────────────────")
    ov = mw_df[mw_df["clone_type"] == "overall"]
    print(ov[["principle", "n_cloned", "mean_cloned", "mean_non_cloned",
               "p_value", "rank_biserial_r", "significant_05"]].to_string(index=False))
    print()
    return mw_df


# ─────────────────────────────────────────────────────────────────────────────
# COMPLEMENTARY ANALYSIS: Per-project logistic regression
# ─────────────────────────────────────────────────────────────────────────────

def run_logistic_regression(df, output_dir, clone_type_filter=None, with_loc=True):
    if clone_type_filter and "clone_type" in df.columns:
        subset = df[(df["clone_type"] == clone_type_filter) | (df["is_cloned"] == 0)].copy()
        label  = clone_type_filter
    else:
        subset = df.copy()
        label  = "overall"

    pred_cols = ["srp", "ocp", "dip"]
    if with_loc and "method_loc" in df.columns:
        pred_cols.append("method_loc")

    subset = subset.dropna(subset=pred_cols + ["is_cloned"])
    for col in pred_cols:
        m, s = subset[col].mean(), subset[col].std()
        subset[f"{col}_z"] = (subset[col] - m) / s if s > 0 else 0.0

    X = sm.add_constant(subset[[f"{c}_z" for c in pred_cols]])
    y = subset["is_cloned"]

    try:
        result = sm.Logit(y, X).fit(disp=0, maxiter=300)
    except Exception as e:
        print(f"  [ERROR] Regression failed ({label}): {e}")
        return None, None, None

    params, conf = result.params, result.conf_int()
    pvals        = result.pvalues
    odds         = np.exp(params)
    odds_lo      = np.exp(conf[0])
    odds_hi      = np.exp(conf[1])

    pname = {"const": "Intercept"}
    for c in pred_cols:
        pname[f"{c}_z"] = c.upper()

    rows = []
    for key, name in pname.items():
        if key not in params.index:
            continue
        rows.append({
            "clone_type"     : label,
            "predictor"      : name,
            "coef"           : round(float(params[key]), 4),
            "odds_ratio"     : round(float(odds[key]), 4),
            "OR_CI_lower_95" : round(float(odds_lo[key]), 4),
            "OR_CI_upper_95" : round(float(odds_hi[key]), 4),
            "p_value"        : round(float(pvals[key]), 4),
            "significant_05" : "Yes" if float(pvals[key]) < 0.05 else "No",
        })

    stats_row = {
        "clone_type"    : label,
        "n_methods"     : int(len(subset)),
        "n_cloned"      : int(y.sum()),
        "log_likelihood": round(float(result.llf), 4),
        "ll_null"       : round(float(result.llnull), 4),
        # McFadden R² vs intercept-only null (per-project standard usage)
        "mcfadden_r2"   : round(float(result.prsquared), 4),
        "AIC"           : round(float(result.aic), 4),
        "converged"     : result.mle_retvals.get("converged", False),
        "controls"      : "+".join(c.upper() for c in pred_cols),
    }
    return rows, stats_row, result


# ─────────────────────────────────────────────────────────────────────────────
# Pooled model: project FE + cluster-robust SEs + correct McFadden null
# ─────────────────────────────────────────────────────────────────────────────

def run_pooled_regression(method_csv, all_clone_csv, output_dir):
    print("\n" + "=" * 70)
    print("POOLED LOGISTIC REGRESSION — ROBUSTNESS CHECK")
    print("Model  : is_cloned ~ SRP+OCP+DIP + LOC + Project FE")
    print("SEs    : clustered by project (conservative; accounts for")
    print("         within-project error correlation)")
    print("R² null: FE + LOC only  (marginal contribution of SOLID)")
    print("=" * 70)

    # ── Load all data ──────────────────────────────────────────────────────
    methods = pd.read_csv(method_csv)
    clones  = pd.read_csv(all_clone_csv)

    # Filter to /src/ paths only — mirrors per-project merge_solid_and_clones
    methods = methods[
        methods["file_path"].astype(str).str.contains("/src/", na=False)
    ].copy()
    methods["file_path"] = methods["file_path"].astype(str).str.strip().apply(normalise_path)
    methods["startline"] = methods["startline"].astype(int)

    raw_col = "file_path_raw" if "file_path_raw" in clones.columns else "file_path"
    clones = clones[
        clones[raw_col].astype(str).str.contains("/src/", na=False)
    ].copy()
    clones["norm_path"] = clones[raw_col].astype(str).apply(normalise_path)
    clones["startline"] = clones["startline"].astype(int)

    if "endline" in methods.columns:
        methods["method_loc"] = (
            methods["endline"].astype(float) - methods["startline"].astype(float) + 1
        ).clip(lower=1)
    else:
        methods["method_loc"] = 1.0

    # Map clone project names to method project names so project is part of
    # the join key — prevents cross-project path collisions.
    clones["project_mapped"] = clones["project"].map(PROJECT_MAP)
    merged = methods.merge(
        clones[["project_mapped", "norm_path", "startline", "is_cloned"]],
        left_on=["project", "file_path", "startline"],
        right_on=["project_mapped", "norm_path", "startline"],
        how="left",
    )
    merged["is_cloned"]     = merged["is_cloned"].fillna(0).astype(int)
    merged["project_clean"] = merged["project"].str.replace(r"_SOLID_Eval$", "", regex=True)

    pred_cols = ["srp", "ocp", "dip", "method_loc"]
    merged    = merged.dropna(subset=pred_cols + ["is_cloned", "project_clean"])

    n, nc = len(merged), merged["is_cloned"].sum()
    print(f"\n  Total methods   : {n:,}  |  Cloned: {nc:,} ({nc/n*100:.1f}%)")
    print(f"  Projects ({merged['project_clean'].nunique()})    :")
    for p, cnt in sorted(merged["project_clean"].value_counts().items()):
        print(f"    {p:<30} {cnt:>8,}")

    # ── Diagnostics on pooled data ─────────────────────────────────────────
    compute_diagnostics(merged, output_dir, label="pooled")

    # ── z-standardise on pooled data ──────────────────────────────────────
    for col in pred_cols:
        m, s = merged[col].mean(), merged[col].std()
        merged[f"{col}_z"] = (merged[col] - m) / s if s > 0 else 0.0

    # ── Project dummies ────────────────────────────────────────────────────
    proj_d  = pd.get_dummies(merged["project_clean"], prefix="proj",
                             drop_first=True, dtype=float)
    z_cols  = [f"{c}_z" for c in pred_cols]
    X_full  = sm.add_constant(pd.concat([merged[z_cols], proj_d], axis=1))

    # Null model: FE + LOC only (no SOLID predictors)
    X_null  = sm.add_constant(
        pd.concat([merged[["method_loc_z"]], proj_d], axis=1)
    )
    y       = merged["is_cloned"]
    proj_id = merged["project_clean"]

    # ── Fit full model with project-clustered SEs ─────────────────────────
    print("\n  Fitting full model (cluster-robust SEs by project)...")
    try:
        fit_full = sm.Logit(y, X_full).fit(
            disp=0, maxiter=500,
            cov_type="cluster",
            cov_kwds={"groups": proj_id},
        )
    except Exception as e:
        print(f"  [ERROR] Full model failed: {e}")
        return

    # ── Fit null model (for marginal R²) ──────────────────────────────────
    print("  Fitting null model (FE + LOC only)...")
    try:
        fit_null = sm.Logit(y, X_null).fit(disp=0, maxiter=500)
    except Exception as e:
        print(f"  [ERROR] Null model failed: {e}")
        return

    # ── Marginal McFadden R² ───────────────────────────────────────────────
    # Measures only the added value of SRP+OCP+DIP over FE+LOC baseline.
    mcf_marginal = 1 - (fit_full.llf / fit_null.llf)

    params   = fit_full.params
    conf     = fit_full.conf_int()
    pvals    = fit_full.pvalues
    odds     = np.exp(params)
    odds_lo  = np.exp(conf.iloc[:, 0])
    odds_hi  = np.exp(conf.iloc[:, 1])

    rows = []
    for key in params.index:
        if key == "const":
            label = "Intercept"
        elif key.endswith("_z"):
            label = key.replace("_z", "").upper()
        else:
            label = "Project: " + key.replace("proj_", "")
        rows.append({
            "predictor"      : label,
            "coef"           : round(float(params[key]), 4),
            "odds_ratio"     : round(float(odds[key]), 4),
            "OR_CI_lower_95" : round(float(odds_lo[key]), 4),
            "OR_CI_upper_95" : round(float(odds_hi[key]), 4),
            "p_value"        : round(float(pvals[key]), 4),
            "significant_05" : "Yes" if float(pvals[key]) < 0.05 else "No",
        })

    res_df = pd.DataFrame(rows)
    res_df.to_csv(os.path.join(output_dir, "pooled_regression_results.csv"), index=False)

    # ── Summary text ──────────────────────────────────────────────────────
    key_set = {"SRP", "OCP", "DIP", "METHOD_LOC"}
    lines   = [
        "POOLED LOGISTIC REGRESSION — ROBUSTNESS CHECK",
        "=" * 62,
        "Model  : is_cloned ~ SRP+OCP+DIP + LOC + Project FE",
        "SEs    : clustered by project (cov_type='cluster')",
        "R² null: intercept + project FE + LOC (marginal SOLID contribution)",
        f"N methods   : {n:,}",
        f"N cloned    : {nc:,} ({nc/n*100:.1f}%)",
        f"N projects  : {merged['project_clean'].nunique()}",
        f"llf full    : {fit_full.llf:.2f}",
        f"llf null    : {fit_null.llf:.2f}",
        f"Marginal R² : {mcf_marginal:.4f}  (SOLID contribution over FE+LOC; NOT variance explained)",
        f"AIC         : {fit_full.aic:.2f}",
        f"Converged   : {fit_full.mle_retvals.get('converged', True)}",
        "",
        "SOLID Predictors (z-standardised, cluster-robust SEs):",
        f"  {'Predictor':<14} {'OR':>8} {'95% CI':>24} {'p':>9}  Sig",
        "  " + "-" * 60,
    ]
    for r in rows:
        if r["predictor"].upper() in key_set:
            ci = f"[{r['OR_CI_lower_95']:.4f}, {r['OR_CI_upper_95']:.4f}]"
            lines.append(f"  {r['predictor']:<14} {r['odds_ratio']:>8.4f} "
                         f"{ci:>24} {r['p_value']:>9.4f}  {r['significant_05']}")
    lines += [
        "",
        "Note: marginal McFadden R² = 1 - (llf_full / llf_null)",
        "      null already includes project FE + MethodLOC.",
        "      This is NOT total model fit and NOT variance explained.",
        "Project fixed effects: see pooled_regression_results.csv.",
    ]
    with open(os.path.join(output_dir, "pooled_regression_summary.txt"), "w") as f:
        f.write("\n".join(lines))

    print("\n── Pooled Model: SOLID Predictors ──────────────────────────────────")
    for r in rows:
        if r["predictor"].upper() in key_set:
            ci = f"[{r['OR_CI_lower_95']:.4f}, {r['OR_CI_upper_95']:.4f}]"
            print(f"  {r['predictor']:<14} OR={r['odds_ratio']:.4f}  "
                  f"95%CI={ci}  p={r['p_value']:.4f}  {r['significant_05']}")
    print(f"\n  Marginal McFadden R² (SOLID over FE+LOC): {mcf_marginal:.4f}")
    return res_df


# ─────────────────────────────────────────────────────────────────────────────
# Summary writer
# ─────────────────────────────────────────────────────────────────────────────

def write_summary_text(all_rows, all_stats, output_dir):
    path = os.path.join(output_dir, "regression_summary.txt")
    with open(path, "w") as f:
        f.write("COMPLEMENTARY LOGISTIC REGRESSION: is_cloned ~ SRP+OCP+DIP+LOC\n")
        f.write("Primary RQ2 analysis: Mann-Whitney U (see mann_whitney_results.csv)\n")
        f.write("McFadden R² = likelihood-ratio index vs intercept-only null.\n")
        f.write("NOT variance explained. Per-project results are DESCRIPTIVE.\n")
        f.write("=" * 70 + "\n\n")
        for s in all_stats:
            f.write(f"Clone Type  : {s['clone_type']}\n")
            f.write(f"  N         : {s['n_methods']:,}  |  Cloned: {s['n_cloned']:,}\n")
            f.write(f"  McF R²    : {s['mcfadden_r2']}  (intercept-only null; NOT var. explained)\n")
            f.write(f"  AIC       : {s['AIC']}\n")
            f.write(f"  Controls  : {s.get('controls','SRP+OCP+DIP')}\n\n")
            sub = [r for r in all_rows if r["clone_type"] == s["clone_type"]]
            f.write(f"  {'Pred':<14} {'OR':>8} {'95% CI':>24} {'p':>9} {'Sig':>5}\n")
            f.write("  " + "-" * 62 + "\n")
            for r in sub:
                ci = f"[{r['OR_CI_lower_95']:.4f}, {r['OR_CI_upper_95']:.4f}]"
                f.write(f"  {r['predictor']:<14} {r['odds_ratio']:>8.4f} "
                        f"{ci:>24} {r['p_value']:>9.4f} {r['significant_05']:>5}\n")
            f.write("\n" + "-" * 70 + "\n\n")
    print(f"  Saved: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method_csv",  required=True)
    parser.add_argument("--clone_csv",   required=True)
    parser.add_argument("--output_dir",  default="./results")
    parser.add_argument("--pooled",      action="store_true",
                        help="Pooled model with project FE + cluster-robust SEs.")
    parser.add_argument("--no_loc",      action="store_true",
                        help="Exclude MethodLOC (sensitivity check only).")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.pooled:
        run_pooled_regression(args.method_csv, args.clone_csv, args.output_dir)
        return

    with_loc = not args.no_loc
    df       = merge_solid_and_clones(args.method_csv, args.clone_csv)

    compute_diagnostics(df, args.output_dir)

    # ── PRIMARY: Mann-Whitney ──────────────────────────────────────────────
    print("Running primary analysis: Mann-Whitney U...")
    run_mann_whitney(df, args.output_dir)

    # ── COMPLEMENTARY: Logistic regression ───────────────────────────────
    print("Running complementary analysis: logistic regression...")
    ctypes = ["overall"]
    if "clone_type" in df.columns:
        ctypes += [t for t in df["clone_type"].unique() if t not in ("none", "overall")]

    all_rows, all_stats = [], []
    for ctype in ctypes:
        out = run_logistic_regression(
            df, args.output_dir,
            clone_type_filter=None if ctype == "overall" else ctype,
            with_loc=with_loc,
        )
        if out[0] is None:
            continue
        rows, stat, _ = out
        all_rows.extend(rows)
        all_stats.append(stat)

    if all_rows:
        pd.DataFrame(all_rows).to_csv(
            os.path.join(args.output_dir, "regression_results.csv"), index=False)
        pd.DataFrame(all_stats).to_csv(
            os.path.join(args.output_dir, "regression_model_stats.csv"), index=False)
        write_summary_text(all_rows, all_stats, args.output_dir)

        print("\n── Complementary Logistic Regression — Overall ──────────────────────")
        for r in all_rows:
            if r["clone_type"] == "overall" and r["predictor"] != "Intercept":
                ci = f"[{r['OR_CI_lower_95']:.4f}, {r['OR_CI_upper_95']:.4f}]"
                print(f"  {r['predictor']:<14} OR={r['odds_ratio']:.4f}  "
                      f"95%CI={ci}  p={r['p_value']:.4f}  {r['significant_05']}")
        print("\n  Per-project = DESCRIPTIVE. Cross-project inference: use --pooled.")


if __name__ == "__main__":
    main()