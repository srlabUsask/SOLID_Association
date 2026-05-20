import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

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
HIGHLIGHT = "#C0392B"

LABEL = {
    "commonslang": "Commons Lang",
    "fitnesse": "FitNesse",
    "hibernate-orm": "Hibernate",
    "jackson-databind_": "Jackson",
    "jmeter": "JMeter",
    "junit5": "JUnit 5",
    "selenium-trunk": "Selenium",
    "struts": "Struts",
}
# Same fixed order used by mw_dotplot and forest_plot:
# Struts at top, FitNesse at bottom.
# matplotlib barh draws first list item at the bottom, so we REVERSE here.
ORDER = ["struts", "junit5", "jmeter", "selenium-trunk",
         "jackson-databind_", "commonslang", "hibernate-orm", "fitnesse"]
ORDER_REVERSED = list(reversed(ORDER))

POOLED = {"SRP": 0.022, "OCP": -0.014, "DIP": 0.140}

df = pd.read_csv("Results/loo_summary/loo_summary.csv")
pivot = df.pivot(index="excluded_project", columns="principle", values="r_rb")
pivot = pivot.reindex(ORDER_REVERSED)[["SRP", "OCP", "DIP"]]

fig, axes = plt.subplots(1, 3, figsize=(9, 3.5), sharey=True,
                         gridspec_kw={"wspace": 0.10})

for ax, principle in zip(axes, ["SRP", "OCP", "DIP"]):
    vals = pivot[principle].values
    labels = [LABEL[p] for p in pivot.index]
    bar_colors = [HIGHLIGHT if p == "struts" else COL[principle] for p in pivot.index]
    bars = ax.barh(labels, vals, color=bar_colors, alpha=0.9,
                   edgecolor="black", linewidth=0.4)
    ax.axvline(0, color="black", linewidth=0.7)
    ax.axvline(POOLED[principle], color="black", linewidth=0.9,
               linestyle="--", label=f"Pooled ({POOLED[principle]:+.3f})")
    ax.set_title(principle, fontweight="bold")
    ax.set_xlabel(r"Pooled $r_{rb}$ with project excluded")
    ax.legend(loc="lower right", framealpha=0.95)
    ax.grid(axis="x", alpha=0.25)

    if principle == "SRP":
        ax.set_xlim(-0.025, 0.05)
    elif principle == "OCP":
        ax.set_xlim(-0.04, 0.01)
    else:
        ax.set_xlim(0.0, 0.20)

    for bar, val in zip(bars, vals):
        offset = 0.0015 if principle != "DIP" else 0.004
        ax.text(val + (offset if val >= 0 else -offset),
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.3f}", va="center",
                ha="left" if val >= 0 else "right", fontsize=5.5)

axes[0].set_ylabel("Project excluded")

# Updated legend: Struts is the largest single-project influence in
# BOTH the SRP sign-flip AND the DIP magnitude reduction.
struts_patch = mpatches.Patch(
    color=HIGHLIGHT,
    label="Struts (flips SRP sign; halves DIP magnitude)"
)
other_patch = mpatches.Patch(color="grey", label="Other projects")
fig.legend(handles=[struts_patch, other_patch], loc="lower center",
           ncol=2, bbox_to_anchor=(0.5, -0.06), frameon=False)

fig.suptitle("Leave-one-out robustness: pooled rank-biserial with each project removed",
             y=1.02, fontweight="bold")

plt.savefig("Results/figures/loo.pdf")
plt.savefig("Results/figures/loo.png", dpi=300)
print("Wrote: Results/figures/loo.{pdf,png}")