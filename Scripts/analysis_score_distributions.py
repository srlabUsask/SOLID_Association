"""
Per-principle score distribution analysis.

Reports the distribution of SRP, OCP, DIP scores (0/1/2) across the
corpus, both pooled and split by clone participation. Demonstrates
the ceiling effect and where genuine variance exists.

"""
import pandas as pd
import numpy as np

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

def main():
    methods = pd.read_csv("Results/per_method_scores.csv")
    methods["norm_path"] = methods["file_path"].apply(normalise_path)
    methods = methods[methods["norm_path"].notna()].copy()

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

    print(f"Corpus: {len(methods)} methods, {methods['is_cloned'].sum()} cloned\n")

    rows = []
    print(f"{'Principle':<10} {'Score':<8} {'Total':>10} {'%':>7} {'Cloned':>10} {'%':>7} {'Non-cloned':>12} {'%':>7}")
    print("-" * 80)

    for p in ["srp", "ocp", "dip"]:
        total = len(methods)
        for score in [0, 1, 2]:
            n_total = (methods[p] == score).sum()
            n_cloned = ((methods[p] == score) & (methods["is_cloned"] == 1)).sum()
            n_non = ((methods[p] == score) & (methods["is_cloned"] == 0)).sum()
            pct_total = 100 * n_total / total
            pct_cloned = 100 * n_cloned / methods["is_cloned"].sum()
            pct_non = 100 * n_non / (total - methods["is_cloned"].sum())
            print(f"{p.upper():<10} {score:<8} {n_total:>10} {pct_total:>6.2f}% "
                  f"{n_cloned:>10} {pct_cloned:>6.2f}% "
                  f"{n_non:>12} {pct_non:>6.2f}%")
            rows.append({
                "principle": p.upper(), "score": score,
                "n_total": int(n_total), "pct_total": pct_total,
                "n_cloned": int(n_cloned), "pct_cloned": pct_cloned,
                "n_non_cloned": int(n_non), "pct_non_cloned": pct_non,
            })
        # Summary stats
        mean = methods[p].mean()
        std = methods[p].std()
        prop_violated = (methods[p] == 0).mean()
        prop_compliant = (methods[p] == 2).mean()
        print(f"{p.upper():<10} {'mean':<8} {mean:>10.3f}  std = {std:.3f}  "
              f"violated = {100*prop_violated:.1f}%  "
              f"compliant = {100*prop_compliant:.1f}%")
        print()

    # Composite SOLID
    print("=== Composite SOLID (SRP + OCP + DIP, range 0-6) ===")
    methods["composite"] = methods["srp"] + methods["ocp"] + methods["dip"]
    for c in range(7):
        n = (methods["composite"] == c).sum()
        pct = 100 * n / len(methods)
        print(f"  Composite = {c}:  n = {n:>8}  ({pct:>5.2f}%)")
    above_4 = (methods["composite"] >= 4).mean()
    print(f"\n  Composite >= 4: {100*above_4:.1f}% of methods")
    print(f"  Composite mean: {methods['composite'].mean():.3f}")

    pd.DataFrame(rows).to_csv("Results/score_distributions.csv", index=False)
    print(f"\nWrote: Results/score_distributions.csv")

if __name__ == "__main__":
    main()