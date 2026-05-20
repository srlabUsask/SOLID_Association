import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np

plt.rcParams.update({
    'font.size': 7, 'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.labelsize': 7, 'axes.titlesize': 8,
    'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'legend.fontsize': 6, 'axes.linewidth': 0.5,
    'savefig.dpi': 600, 'savefig.bbox': 'tight',
    'pdf.fonttype': 42, 'ps.fonttype': 42,
})

COL = {"SRP": "#B5651D", "OCP": "#2E6B8A", "DIP": "#3B6E5A"}

PROJECT_LABEL = {
    "struts": "Struts",
    "junit5": "JUnit 5",
    "jmeter": "JMeter",
    "selenium-trunk": "Selenium",
    "jackson-databind_": "Jackson",
    "commonslang": "Commons Lang",
    "hibernate-orm": "Hibernate",
    "fitnesse": "FitNesse",
}
FIXED_ORDER = ["struts", "junit5", "jmeter", "selenium-trunk",
               "jackson-databind_", "commonslang", "hibernate-orm", "fitnesse"]

# Bonferroni over the 24-comparison family (8 projects × 3 principles)
ALPHA_TIERS = [0.05/24, 0.01/24, 0.001/24]

df = pd.read_csv("Results/rq1_analysis/per_project_method_comparison.csv")

fig, axes = plt.subplots(3, 1, figsize=(9, 5.5), sharex=True,
                         gridspec_kw={"hspace": 0.30})

x = np.arange(len(FIXED_ORDER))

for ax, principle in zip(axes, ["SRP", "OCP", "DIP"]):
    col = COL[principle]
    sub = df[df["principle"] == principle].copy()
    sub["project"] = pd.Categorical(sub["project"], categories=FIXED_ORDER, ordered=True)
    sub = sub.sort_values("project")

    ax.axhspan(-0.10, 0.10, color="lightgrey", alpha=0.40, zorder=0)
    ax.axhline(0, color="black", lw=0.8, zorder=1)
    ax.axhline(-0.10, color="grey", lw=0.6, ls=":", zorder=1)
    ax.axhline(+0.10, color="grey", lw=0.6, ls=":", zorder=1)
    ax.axhline(-0.30, color="grey", lw=0.5, ls=":", alpha=0.6, zorder=1)
    ax.axhline(+0.30, color="grey", lw=0.5, ls=":", alpha=0.6, zorder=1)

    for i, (_, row) in enumerate(sub.iterrows()):
        rrb = row["r_rb"]
        p = row["p_value"]
        sig = p < ALPHA_TIERS[0]
        if sig:
            ax.plot(i, rrb, marker="D", ms=8, color=col,
                    markeredgecolor=col, zorder=3)
        else:
            ax.plot(i, rrb, marker="o", ms=7, color="white",
                    markeredgecolor=col, mew=1.0, zorder=3)

    ax.set_ylim(-0.35, 0.45)
    ax.set_ylabel(f"{principle}\n" + r"$r_{rb}$", fontweight="bold")

axes[-1].set_xticks(x)
axes[-1].set_xticklabels([PROJECT_LABEL[p].replace(" ", "\n") for p in FIXED_ORDER],
                         fontsize=6)

import matplotlib.lines as mlines
sig_marker = mlines.Line2D([], [], marker="D", color="black",
                           markerfacecolor="black", linestyle="None",
                           label=f"p < {ALPHA_TIERS[0]:.4f} (Bonferroni, k=24)")
ns_marker = mlines.Line2D([], [], marker="o", color="black",
                          markerfacecolor="white", linestyle="None",
                          label="n.s.")
neg_band = mpatches.Patch(color="lightgrey", alpha=0.5, label="negligible: |r_rb| < 0.10")

fig.legend(handles=[sig_marker, ns_marker, neg_band],
           loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02),
           frameon=False)

fig.suptitle("Per-project Mann–Whitney rank-biserial: SOLID vs. clone participation",
             y=0.995, fontweight="bold")

plt.savefig("Results/figures/mw_dotplot.pdf")
plt.savefig("Results/figures/mw_dotplot.png", dpi=300)
print("Wrote: Results/figures/mw_dotplot.{pdf,png}")