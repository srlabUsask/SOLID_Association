import os
import argparse
import pandas as pd
import numpy as np
from scipy import stats


# ─────────────────────────────────────────────────────────────────────────────
# Project name mapping  (clone CSV project name → method CSV project name)
# Keep in sync with regression_rq2.py — consider extracting to shared config.py
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

DISPLAY_NAMES = {
    "commonslang"       : "Commons Lang",
    "fitnesse"          : "FitNesse",
    "hibernate-orm"     : "Hibernate ORM",
    "jackson-databind_" : "Jackson Databind",
    "jmeter"            : "JMeter",
    "junit5"            : "JUnit 5",
    "selenium-trunk"    : "Selenium",
    "struts"            : "Struts",
}

# Clone type priority for deduplication (Fix #3)
_TYPE_PRIORITY = {"T3": 3, "T2": 2, "T1": 1, "none": 0}


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def normalise_path(p):
    if isinstance(p, str) and "/src/" in p:
        return p.split("/src/")[-1]
    raise ValueError(
        f"normalise_path called on path without '/src/': {p!r}. "
        "Pre-filter the dataframe to rows containing '/src/' before calling."
    )


def bonf_stars(p_val, n_tests):
    if np.isnan(p_val) or n_tests <= 0:
        return ''
    if p_val < 0.001 / n_tests:
        return '***'
    if p_val < 0.010 / n_tests:
        return '**'
    if p_val < 0.050 / n_tests:
        return '*'
    return ''


def fmt_p(p_val):
    if np.isnan(p_val):
        return 'NaN'
    if p_val < 1e-300:
        return 'p < 10^{-300}'
    if p_val < 1e-4:
        exp = int(np.floor(np.log10(p_val)))
        return f'p < 10^{{{exp}}}'
    return f'p = {p_val:.4f}'


# ─────────────────────────────────────────────────────────────────────────────
# Data loading and merging
# ─────────────────────────────────────────────────────────────────────────────

def load_and_merge_data(method_csv, clone_csv):
    print(f"Loading method scores from: {method_csv}")
    methods = pd.read_csv(method_csv)
    print(f"  → Loaded {len(methods):,} method records")

    print(f"Loading clone data from: {clone_csv}")
    clones = pd.read_csv(clone_csv)
    print(f"  → Loaded {len(clones):,} clone records")

    # ── Prepare METHOD side ──────────────────────────────────────────────────
    # Fix #4: Do NOT filter methods to /src/ here.
    # Normalise the path for join key — only safe to call on /src/ paths,
    # so we normalise conditionally and keep non-/src/ paths as-is for now.
    # The join will simply not match them (left join → is_cloned stays 0).
    def safe_normalise(p):
        s = str(p).strip()
        if "/src/" in s:
            return s.split("/src/")[-1]
        return None  # will not match clone keys; excluded from linked corpus

    methods["norm_path"] = methods["file_path"].apply(safe_normalise)
    methods["startline"] = methods["startline"].astype(int)

    # ── Prepare CLONE side ───────────────────────────────────────────────────
    raw_col = "file_path_raw" if "file_path_raw" in clones.columns else "file_path"
    clones = clones[
        clones[raw_col].astype(str).str.contains("/src/", na=False)
    ].copy()
    clones["norm_path"] = clones[raw_col].astype(str).apply(normalise_path)
    clones["startline"] = clones["startline"].astype(int)
    clones["project_mapped"] = clones["project"].map(PROJECT_MAP)

    # ── Merge ────────────────────────────────────────────────────────────────
    clone_cols = ["project_mapped", "norm_path", "startline",
                  "is_cloned", "clone_type", "nclasses"]
    if "clone_nlines" in clones.columns:
        clone_cols.append("clone_nlines")

    merged = methods.merge(
        clones[clone_cols],
        left_on=["project", "norm_path", "startline"],
        right_on=["project_mapped", "norm_path", "startline"],
        how="left",
        indicator=True
    )

    # Fill non-cloned methods
    merged["is_cloned"]  = merged["is_cloned"].fillna(0).astype(int)
    merged["clone_type"] = merged["clone_type"].fillna("none")
    merged["nclasses"]   = merged["nclasses"].fillna(0).astype(int)

    # Derived column
    merged["method_loc"] = merged["endline"] - merged["startline"] + 1

    # ── Diagnostics ──────────────────────────────────────────────────────────
    print("\nMerge summary:")
    print(merged["_merge"].value_counts().to_string())
    n_linked = (merged["_merge"] == "both").sum()
    n_total  = len(merged)
    n_cloned = merged["is_cloned"].sum()
    print(f"  Linked methods (both):  {n_linked:,}")
    print(f"  Unlinked methods (left_only): {n_total - n_linked:,}")
    print(f"  Total methods in merged df:   {n_total:,}")
    print(f"  Cloned methods:               {n_cloned:,}")
    print(f"  Clone rate (linked corpus):   "
          f"{n_cloned / n_linked * 100:.2f}%  "
          f"[NOTE: method_level_analysis uses linked corpus only]")

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# System-level analysis
# ─────────────────────────────────────────────────────────────────────────────

def system_level_analysis(df, output_dir):
    print("\n" + "=" * 70)
    print("SYSTEM-LEVEL ANALYSIS")
    print("=" * 70)

    # Composite score (Fix #7)
    df = df.copy()
    df["solid_composite"] = df["srp"] + df["ocp"] + df["dip"]

    results = []

    for proj_key in sorted(PROJECT_MAP.keys()):
        proj_name = PROJECT_MAP[proj_key]
        proj_df   = df[df["project"] == proj_name].copy()

        # Fix #5 (carried forward): raise rather than silently skip, so
        # PROJECT_MAP mismatches are caught immediately.
        assert len(proj_df) > 0, (
            f"No rows found for project key '{proj_key}' → '{proj_name}'. "
            "Check that PROJECT_MAP values match the 'project' column in "
            "per_method_scores.csv."
        )

        n_total  = len(proj_df)
        n_cloned = proj_df["is_cloned"].sum()
        clone_rate = n_cloned / n_total

        # Overall mean SOLID scores
        mean_srp = proj_df["srp"].mean()
        mean_ocp = proj_df["ocp"].mean()
        mean_dip = proj_df["dip"].mean()

        # Fix #7: composite statistics
        mean_composite  = proj_df["solid_composite"].mean()
        prop_strong     = (proj_df["solid_composite"] >= 4).mean()

        # Cloned vs non-cloned means
        cloned     = proj_df[proj_df["is_cloned"] == 1]
        non_cloned = proj_df[proj_df["is_cloned"] == 0]

        def safe_mean(sub, col):
            return sub[col].mean() if len(sub) > 0 else np.nan

        # Clone type breakdown — NOTE: may double-count methods in multiple
        # clone classes. For accurate counts see clone_type_analysis() which
        # deduplicates. These counts are provided here as quick diagnostics only.
        t1_diag = (proj_df["clone_type"] == "T1").sum()
        t2_diag = (proj_df["clone_type"] == "T2").sum()
        t3_diag = (proj_df["clone_type"] == "T3").sum()

        results.append({
            "project":              proj_key,
            "display_name":         DISPLAY_NAMES[proj_key],
            "n_methods":            n_total,
            "n_cloned":             n_cloned,
            "clone_rate":           clone_rate,
            "mean_srp":             mean_srp,
            "mean_ocp":             mean_ocp,
            "mean_dip":             mean_dip,
            "mean_composite":       mean_composite,   # Fix #7
            "prop_strong_solid":    prop_strong,      # Fix #7
            "mean_srp_cloned":      safe_mean(cloned, "srp"),
            "mean_ocp_cloned":      safe_mean(cloned, "ocp"),
            "mean_dip_cloned":      safe_mean(cloned, "dip"),
            "mean_srp_non_cloned":  safe_mean(non_cloned, "srp"),
            "mean_ocp_non_cloned":  safe_mean(non_cloned, "ocp"),
            "mean_dip_non_cloned":  safe_mean(non_cloned, "dip"),
            "n_t1_diag":            t1_diag,
            "n_t2_diag":            t2_diag,
            "n_t3_diag":            t3_diag,
        })

        print(f"\n{DISPLAY_NAMES[proj_key]}")
        print(f"  Methods: {n_total:,} ({n_cloned:,} cloned, {clone_rate*100:.1f}%)")
        print(f"  Mean scores: SRP={mean_srp:.3f}, OCP={mean_ocp:.3f}, "
              f"DIP={mean_dip:.3f}, composite={mean_composite:.3f}")
        print(f"  Prop. strong (SOLID≥4): {prop_strong*100:.1f}%")
        print(f"  Clone type counts (pre-dedup): T1={t1_diag}, T2={t2_diag}, T3={t3_diag}")

    df_results = pd.DataFrame(results)
    out_path   = os.path.join(output_dir, "system_level_summary.csv")
    df_results.to_csv(out_path, index=False)
    print(f"\n→ Saved: {out_path}")
    return df_results


# ─────────────────────────────────────────────────────────────────────────────
# Method-level analysis  (Fix #6: uses linked corpus only)
# ─────────────────────────────────────────────────────────────────────────────

def method_level_analysis(df, output_dir):
    print("\n" + "=" * 70)
    print("METHOD-LEVEL ANALYSIS  (linked corpus only)")
    print("=" * 70)

    cloned     = df[df["is_cloned"] == 1]
    non_cloned = df[df["is_cloned"] == 0]

    print(f"\nLinked corpus:")
    print(f"  Total:      {len(df):,}")
    print(f"  Cloned:     {len(cloned):,} ({len(cloned)/len(df)*100:.1f}%)")
    print(f"  Non-cloned: {len(non_cloned):,} ({len(non_cloned)/len(df)*100:.1f}%)")

    results = []

    for principle in ["srp", "ocp", "dip"]:
        c_vals  = cloned[principle].dropna()
        nc_vals = non_cloned[principle].dropna()

        mean_c   = c_vals.mean()
        mean_nc  = nc_vals.mean()
        med_c    = c_vals.median()
        med_nc   = nc_vals.median()
        std_c    = c_vals.std()
        std_nc   = nc_vals.std()

        # Mann-Whitney U (cloned vs non-cloned)
        u_stat, p_val = stats.mannwhitneyu(c_vals, nc_vals, alternative="two-sided")

        n1   = len(c_vals)
        n2   = len(nc_vals)
        r_rb = 1 - (2 * u_stat) / (n1 * n2)   # positive → cloned ranks lower

        # Cohen's d (secondary, parametric)
        pooled_std = np.sqrt(((n1-1)*std_c**2 + (n2-1)*std_nc**2) / (n1+n2-2))
        cohens_d   = (mean_c - mean_nc) / pooled_std if pooled_std > 0 else 0.0

        results.append({
            "principle":       principle.upper(),
            "n_cloned":        n1,
            "n_non_cloned":    n2,
            "mean_cloned":     mean_c,
            "mean_non_cloned": mean_nc,
            "median_cloned":   med_c,
            "median_non_cloned": med_nc,
            "std_cloned":      std_c,
            "std_non_cloned":  std_nc,
            "mann_whitney_u":  u_stat,
            "p_value":         p_val,
            "r_rb":            r_rb,
            "cohens_d":        cohens_d,
        })

        print(f"\n{principle.upper()}:")
        print(f"  Cloned:     mean={mean_c:.3f}, median={med_c:.1f}, std={std_c:.3f}")
        print(f"  Non-cloned: mean={mean_nc:.3f}, median={med_nc:.1f}, std={std_nc:.3f}")
        print(f"  Δ (cloned − non-cloned): {mean_c - mean_nc:+.3f}")
        print(f"  Mann-Whitney U: {u_stat:,.0f},  {fmt_p(p_val)},  r_rb={r_rb:+.4f}")
        print(f"  Cohen's d: {cohens_d:+.4f}")

    df_results = pd.DataFrame(results)
    out_path   = os.path.join(output_dir, "method_level_summary.csv")
    df_results.to_csv(out_path, index=False)
    print(f"\n→ Saved: {out_path}")
    return df_results


# ─────────────────────────────────────────────────────────────────────────────
# Per-project method-level breakdown  (Fix #2, #6)
# ─────────────────────────────────────────────────────────────────────────────

def per_project_method_analysis(df, output_dir):
    print("\n" + "=" * 70)
    print("PER-PROJECT METHOD-LEVEL ANALYSIS  (linked corpus only)")
    print("=" * 70)

    rows = []

    for proj_key in sorted(PROJECT_MAP.keys()):
        proj_name = PROJECT_MAP[proj_key]
        proj_df   = df[df["project"] == proj_name].copy()

        if len(proj_df) == 0:
            continue

        cloned     = proj_df[proj_df["is_cloned"] == 1]
        non_cloned = proj_df[proj_df["is_cloned"] == 0]

        if len(cloned) == 0 or len(non_cloned) == 0:
            print(f"\n{DISPLAY_NAMES[proj_key]}: skipped (no cloned or no non-cloned methods)")
            continue

        print(f"\n{DISPLAY_NAMES[proj_key]}")

        for principle in ["srp", "ocp", "dip"]:
            c_vals  = cloned[principle].dropna()
            nc_vals = non_cloned[principle].dropna()

            if len(c_vals) > 0 and len(nc_vals) > 0:
                u_stat, p_val = stats.mannwhitneyu(c_vals, nc_vals, alternative="two-sided")
                n1   = len(c_vals)
                n2   = len(nc_vals)
                r_rb = 1 - (2 * u_stat) / (n1 * n2)
            else:
                u_stat = p_val = r_rb = np.nan

            mean_c  = c_vals.mean()  if len(c_vals)  > 0 else np.nan
            mean_nc = nc_vals.mean() if len(nc_vals) > 0 else np.nan

            rows.append({
                "project":         proj_key,
                "display_name":    DISPLAY_NAMES[proj_key],
                "principle":       principle.upper(),
                "mean_cloned":     mean_c,
                "mean_non_cloned": mean_nc,
                "diff":            (mean_c - mean_nc) if not (np.isnan(mean_c) or np.isnan(mean_nc)) else np.nan,
                "mann_whitney_u":  u_stat,
                "p_value":         p_val,
                "r_rb":            r_rb,
                # bonf_stars filled below once n_tests is known
            })

            print(f"  {principle.upper()}: cloned={mean_c:.3f}, non-cloned={mean_nc:.3f}, "
                  f"diff={mean_c - mean_nc:+.3f},  {fmt_p(p_val)},  r_rb={r_rb:+.4f}")

    # ── Fix #2: three-tier Bonferroni over ALL comparisons in this table ─────
    n_tests = sum(1 for r in rows if not np.isnan(r["p_value"]))
    print(f"\nBonferroni family size: {n_tests} comparisons")
    print(f"  * threshold:   p < {0.050/n_tests:.5f}")
    print(f"  ** threshold:  p < {0.010/n_tests:.5f}")
    print(f"  *** threshold: p < {0.001/n_tests:.5f}")

    for r in rows:
        r["bonf_stars"] = bonf_stars(r["p_value"], n_tests)

    df_results = pd.DataFrame(rows)
    out_path   = os.path.join(output_dir, "per_project_method_comparison.csv")
    df_results.to_csv(out_path, index=False)
    print(f"\n→ Saved: {out_path}")
    return df_results


# ─────────────────────────────────────────────────────────────────────────────
# Clone type distribution  (Fix #3: deduplication by type priority)
# ─────────────────────────────────────────────────────────────────────────────

def clone_type_analysis(df, output_dir):

    print("\n" + "=" * 70)
    print("CLONE TYPE ANALYSIS  (deduplicated by type priority)")
    print("=" * 70)

    cloned_df = df[df["is_cloned"] == 1].copy()
    cloned_df["type_rank"] = cloned_df["clone_type"].map(_TYPE_PRIORITY).fillna(0)

    # Deduplicate: keep highest-priority type per method identity
    deduped = (
        cloned_df
        .sort_values("type_rank", ascending=False)
        .drop_duplicates(subset=["project", "norm_path", "startline"])
    )

    print(f"\nCloned methods before dedup: {len(cloned_df):,}")
    print(f"Cloned methods after  dedup: {len(deduped):,}")

    results = []

    for clone_type in ["T1", "T2", "T3"]:
        ct_df = deduped[deduped["clone_type"] == clone_type]
        n = len(ct_df)
        if n == 0:
            continue

        small_sample_warning = " [CAUTION: n < 30, estimates unreliable]" if n < 30 else ""

        for principle in ["srp", "ocp", "dip"]:
            results.append({
                "clone_type": clone_type,
                "principle":  principle.upper(),
                "n":          n,
                "mean":       ct_df[principle].mean(),
                "median":     ct_df[principle].median(),
                "std":        ct_df[principle].std(),
            })

        print(f"\n{clone_type} clones (n={n:,}){small_sample_warning}:")
        print(f"  SRP: mean={ct_df['srp'].mean():.3f}, median={ct_df['srp'].median():.1f}")
        print(f"  OCP: mean={ct_df['ocp'].mean():.3f}, median={ct_df['ocp'].median():.1f}")
        print(f"  DIP: mean={ct_df['dip'].mean():.3f}, median={ct_df['dip'].median():.1f}")

    df_results = pd.DataFrame(results)
    out_path   = os.path.join(output_dir, "clone_type_distributions.csv")
    df_results.to_csv(out_path, index=False)
    print(f"\n→ Saved: {out_path}")
    return df_results


# ─────────────────────────────────────────────────────────────────────────────
# Summary text output
# ─────────────────────────────────────────────────────────────────────────────

def generate_summary_text(system_df, method_df, linked_n, output_dir):
    out_path = os.path.join(output_dir, "rq1_summary.txt")

    total_methods = system_df["n_methods"].sum()
    total_cloned  = system_df["n_cloned"].sum()
    min_rate      = system_df["clone_rate"].min() * 100
    max_rate      = system_df["clone_rate"].max() * 100

    with open(out_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("RQ1 ANALYSIS SUMMARY  (analysis_rq1.py v2.0)\n")
        f.write("=" * 70 + "\n\n")

        f.write("Research Question:\n")
        f.write("How does variation in measured SOLID structural signals relate to\n")
        f.write("clone participation in mature Java systems?\n\n")

        f.write("=" * 70 + "\n")
        f.write("CORPUS STATISTICS\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total projects:              {len(system_df)}\n")
        f.write(f"Total methods (all):         {total_methods:,}\n")
        f.write(f"Linked methods (both sides): {linked_n:,}  "
                f"[method-level analyses use this corpus]\n")
        f.write(f"Total cloned methods:        {total_cloned:,}\n")
        f.write(f"Overall clone rate:          {total_cloned/total_methods*100:.2f}%\n\n")

        f.write("=" * 70 + "\n")
        f.write("SYSTEM-LEVEL FINDINGS\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Clone rate range: {min_rate:.0f}%–{max_rate:.0f}%\n\n")

        f.write("Clone rate by project (descending):\n")
        for _, row in system_df.sort_values("clone_rate", ascending=False).iterrows():
            f.write(f"  {row['display_name']:20s}: {row['clone_rate']*100:5.1f}%  "
                    f"({row['n_cloned']:,}/{row['n_methods']:,})  "
                    f"composite={row['mean_composite']:.3f}  "
                    f"prop_strong={row['prop_strong_solid']*100:.1f}%\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("METHOD-LEVEL FINDINGS  (linked corpus, N=" + f"{linked_n:,})\n")
        f.write("=" * 70 + "\n\n")

        for _, row in method_df.iterrows():
            p_str = fmt_p(row["p_value"])
            f.write(f"{row['principle']}:\n")
            f.write(f"  Cloned:       mean={row['mean_cloned']:.3f}, "
                    f"median={row['median_cloned']:.1f}\n")
            f.write(f"  Non-cloned:   mean={row['mean_non_cloned']:.3f}, "
                    f"median={row['median_non_cloned']:.1f}\n")
            f.write(f"  Difference:   {row['mean_cloned'] - row['mean_non_cloned']:+.3f}\n")
            f.write(f"  Mann-Whitney: U={row['mann_whitney_u']:,.0f},  {p_str}\n")
            f.write(f"  Effect size:  r_rb={row['r_rb']:+.4f},  "
                    f"Cohen's d={row['cohens_d']:+.4f}\n\n")

        f.write("=" * 70 + "\n")
        f.write("INTERPRETATION NOTES\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"1. Clone rates vary {max_rate/min_rate:.1f}-fold across projects "
                f"({min_rate:.0f}%–{max_rate:.0f}%)\n")
        f.write("2. Positive r_rb → cloned methods rank LOWER (worse compliance)\n")
        f.write("   Sign set by mannwhitneyu(cloned, non_cloned) argument order\n")
        f.write("3. Higher SOLID scores = stronger compliance (fewer detected violations)\n")
        f.write("4. SOLID(m) composite = SRP + OCP + DIP ∈ [0, 6]; strong = ≥ 4\n")
        f.write("5. See per_project_method_comparison.csv for Bonferroni star labels\n")
        f.write("6. Clone type counts in clone_type_distributions.csv are deduplicated\n")
        f.write("   (T3 > T2 > T1 priority per method); system_level_summary.csv\n")
        f.write("   n_t*_diag columns are PRE-dedup diagnostic counts only\n")

    print(f"\n→ Saved: {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RQ1 v2.0: SOLID score variation and clone participation analysis"
    )
    parser.add_argument("--method_csv",  required=True,
                        help="Path to per_method_scores.csv")
    parser.add_argument("--clone_csv",   required=True,
                        help="Path to ALL_PROJECTS_clone_methods.csv")
    parser.add_argument("--output_dir",  required=True,
                        help="Output directory for results")
    parser.add_argument("--exclude_project", default=None,
                        help="Optional: project key to exclude from analysis (for leave-one-out)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ── Load & merge ─────────────────────────────────────────────────────────
    df = load_and_merge_data(args.method_csv, args.clone_csv)

    linked_df = df[df["norm_path"].notna()].copy()
    if args.exclude_project:
        excluded_score_name = PROJECT_MAP.pop(args.exclude_project)
        linked_df = linked_df[linked_df["project"] != excluded_score_name].copy()
        print(f"Excluded project: {args.exclude_project} → {excluded_score_name}")
        print(f"Remaining methods: {len(linked_df):,}")
    linked_n  = len(linked_df)
    print(f"\nLinked corpus for method-level analyses: {linked_n:,} methods")
    print(f"  (methods with /src/ paths: {linked_df['is_cloned'].sum():,} cloned, "
          f"{(linked_df['is_cloned'] == 0).sum():,} non-cloned)")

    # ── Analyses ─────────────────────────────────────────────────────────────
    system_df    = system_level_analysis(linked_df, args.output_dir)  # /src/ corpus (92,415)
    method_df    = method_level_analysis(linked_df, args.output_dir)  # /src/ corpus
    per_proj_df  = per_project_method_analysis(linked_df, args.output_dir)  # /src/ corpus
    clone_type_df = clone_type_analysis(linked_df, args.output_dir)  # /src/ corpus, deduped

    # ── Summary ──────────────────────────────────────────────────────────────
    generate_summary_text(system_df, method_df, linked_n, args.output_dir)

    print("\n" + "=" * 70)
    print("RQ1 ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\nAll outputs saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
