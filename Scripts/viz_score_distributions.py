import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

df = pd.read_csv("Results/score_distributions.csv")

PRINCIPLES = ["SRP", "OCP", "DIP"]
SCORE_LABELS = {0: "Violated (0)", 1: "Insufficient evidence (1)", 2: "Compliant (2)"}
SCORE_COLORS = {0: "#C0392B", 1: "#F39C12", 2: "#27AE60"}

fig, axes = plt.subplots(1, 3, figsize=(9, 3.5), sharey=True,
                         gridspec_kw={"wspace": 0.10})

for ax, principle in zip(axes, PRINCIPLES):
    sub = df[df["principle"] == principle].sort_values("score")
    pct_cloned = sub["pct_cloned"].values
    pct_non = sub["pct_non_cloned"].values

    x = np.array([0, 1])  # cloned at x=0, non-cloned at x=1

    bottom_cloned = 0
    bottom_non = 0
    for i, score in enumerate([0, 1, 2]):
        row = sub.iloc[i]
        c = SCORE_COLORS[score]
        # Cloned bar
        ax.bar(0, row["pct_cloned"], bottom=bottom_cloned,
               color=c, edgecolor="black", linewidth=0.4,
               label=SCORE_LABELS[score] if principle == "SRP" else None,
               width=0.6)
        # Non-cloned bar
        ax.bar(1, row["pct_non_cloned"], bottom=bottom_non,
               color=c, edgecolor="black", linewidth=0.4, width=0.6)

        # Label percentages on bars (only if >= 4%)
        if row["pct_cloned"] >= 4:
            ax.text(0, bottom_cloned + row["pct_cloned"]/2,
                    f"{row['pct_cloned']:.1f}%",
                    ha="center", va="center", fontsize=7,
                    color="white" if score != 1 else "black",
                    fontweight="bold")
        if row["pct_non_cloned"] >= 4:
            ax.text(1, bottom_non + row["pct_non_cloned"]/2,
                    f"{row['pct_non_cloned']:.1f}%",
                    ha="center", va="center", fontsize=7,
                    color="white" if score != 1 else "black",
                    fontweight="bold")

        bottom_cloned += row["pct_cloned"]
        bottom_non += row["pct_non_cloned"]

    ax.set_xticks(x)
    ax.set_xticklabels(["Cloned", "Non-cloned"])
    ax.set_title(principle, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_xlim(-0.6, 1.6)
    ax.grid(axis="y", alpha=0.25)

axes[0].set_ylabel("Percentage of methods")

fig.legend(loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04),
           frameon=False, fontsize=7)

fig.suptitle("Score distributions by clone status: DIP carries the discriminative variance",
             y=1.02, fontweight="bold")

plt.savefig("Results/figures/score_distributions.pdf")
plt.savefig("Results/figures/score_distributions.png", dpi=300)
print("Wrote: Results/figures/score_distributions.{pdf,png}")