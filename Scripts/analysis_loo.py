"""
Leave-one-out robustness analysis for RQ1.

Runs analysis_rq1.py 8 times, each time excluding one project, and
collates the pooled SRP/OCP/DIP rank-biserial coefficients into a
single summary CSV.
"""

import os
import argparse
import subprocess
import pandas as pd

PROJECTS = [
    "commonslang",
    "fitnesse",
    "hibernate-orm",
    "jackson-databind_",
    "jmeter",
    "junit5",
    "selenium-trunk",
    "struts",
]

def main():
    parser = argparse.ArgumentParser(
        description="Leave-one-out robustness analysis for RQ1"
    )
    parser.add_argument("--method_csv", required=True)
    parser.add_argument("--clone_csv", required=True)
    parser.add_argument("--output_dir", required=True,
                        help="Directory to write loo_summary.csv. "
                             "Per-project outputs go to Results/loo_<project>/")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    rows = []
    for proj in PROJECTS:
        out_dir = f"Results/loo_{proj}"
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n=== Running leave-one-out without {proj} ===")
        subprocess.run([
            "python", "Scripts/analysis_rq1.py",
            "--method_csv", args.method_csv,
            "--clone_csv", args.clone_csv,
            "--output_dir", out_dir,
            "--exclude_project", proj,
        ], check=True, stdout=subprocess.DEVNULL)

        summary = pd.read_csv(f"{out_dir}/method_level_summary.csv")
        for _, r in summary.iterrows():
            rows.append({
                "excluded_project": proj,
                "principle": r["principle"],
                "n_cloned": r["n_cloned"],
                "n_non_cloned": r["n_non_cloned"],
                "r_rb": r["r_rb"],
                "p_value": r["p_value"],
            })

    out_path = os.path.join(args.output_dir, "loo_summary.csv")
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\nWrote leave-one-out summary to: {out_path}")
    print("\nSummary (pooled r_rb per excluded project):")
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="excluded_project", columns="principle", values="r_rb")
    pivot = pivot[["SRP", "OCP", "DIP"]]
    print(pivot.round(4).to_string())

if __name__ == "__main__":
    main()