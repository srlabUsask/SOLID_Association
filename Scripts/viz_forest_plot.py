import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

plt.rcParams.update({
    'font.size': 7, 'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.labelsize': 7, 'axes.titlesize': 8,
    'xtick.labelsize': 6, 'ytick.labelsize': 6,
    'legend.fontsize': 6, 'axes.linewidth': 0.5,
    'savefig.dpi': 600, 'savefig.bbox': 'tight',
    'pdf.fonttype': 42, 'ps.fonttype': 42,
})

COL = {"SRP": "#B5651D", "OCP": "#2E6B8A", "DIP": "#3B6E5A"}

PROJECT_DIRS = {
    "Struts": "struts",
    "JUnit 5": "junit5",
    "JMeter": "jmeter",
    "Selenium": "selenium-trunk",
    "Jackson": "jackson-databind_",
    "Commons Lang": "commonslang",
    "Hibernate": "hibernate-orm",
    "FitNesse": "fitnesse",
}
FIXED_ORDER = ["Struts", "JUnit 5", "JMeter", "Selenium",
               "Jackson", "Commons Lang", "Hibernate", "FitNesse"]

# Bonferroni within project, k=3 (SRP, OCP, DIP per project)
ALPHA = 0.05 / 3

# Load per-project ORs
records = []
for label, dirname in PROJECT_DIRS.items():
    path = f"Results/{dirname}/regression_results.csv"
    df = pd.read_csv(path)
    df = df[df["clone_type"] == "overall"]
    for principle in ["SRP", "OCP", "DIP"]:
        row = df[df["predictor"] == principle]
        if len(row) == 0:
            records.append((label, principle, None, None, None, 1.0))
            continue
        r = row.iloc[0]
        records.append((label, principle,
                        r["odds_ratio"],
                        r["OR_CI_lower_95"], r["OR_CI_upper_95"],
                        r["p_value"]))

data = pd.DataFrame(records, columns=["project", "principle", "OR", "lo", "hi", "p"])

fig, axes = plt.subplots(1, 3, figsize=(9, 4.5), sharey=True,
                         gridspec_kw={"wspace": 0.12})

for ax, principle in zip(axes, ["SRP", "OCP", "DIP"]):
    col = COL[principle]
    sub = data[data["principle"] == principle].copy()
    sub["project"] = pd.Categorical(sub["project"], categories=FIXED_ORDER, ordered=True)
    sub = sub.sort_values("project")
    ys = np.arange(len(sub))[::-1]  # top to bottom = FIXED_ORDER

    for y, (_, row) in zip(ys, sub.iterrows()):
        if pd.isna(row["OR"]):
            ax.plot([], [])
            continue
        sig = row["p"] < ALPHA
        marker = "D" if sig else "o"
        face = col if sig else "white"
        ax.plot(row["OR"], y, marker=marker, ms=7, color=col,
                markerfacecolor=face, markeredgecolor=col, mew=1.0)
        if not (pd.isna(row["lo"]) or pd.isna(row["hi"])):
            ax.plot([row["lo"], row["hi"]], [y, y], color=col, lw=1.0)

    ax.axvline(1.0, color="black", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlim(0.4, 3.0)
    ax.set_yticks(ys)
    ax.set_yticklabels(sub["project"].astype(str))
    ax.set_xlabel("Odds Ratio (log scale)")
    ax.set_title(principle, fontweight="bold")
    ax.grid(axis="x", alpha=0.25, which="both")

import matplotlib.lines as mlines
sig_marker = mlines.Line2D([], [], marker="D", color="black",
                           markerfacecolor="black", linestyle="None",
                           label="p < 0.017 (Bonferroni)")
ns_marker = mlines.Line2D([], [], marker="o", color="black",
                          markerfacecolor="white", linestyle="None",
                          label="n.s.")
fig.legend(handles=[sig_marker, ns_marker], loc="lower center",
           ncol=2, bbox_to_anchor=(0.5, -0.02), frameon=False)

fig.suptitle("Per-project odds ratios (MethodLOC-controlled logistic regression)",
             y=1.02, fontweight="bold")

plt.savefig("Results/figures/forest_plot.pdf")
plt.savefig("Results/figures/forest_plot.png", dpi=300)
print("Wrote: Results/figures/forest_plot.{pdf,png}")