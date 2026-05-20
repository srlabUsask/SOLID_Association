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

df = pd.read_csv("Results/nicad_eligible_results.csv")
pivot = df.pivot(index="principle", columns="subset", values="r_rb")
pivot = pivot.loc[["SRP", "OCP", "DIP"]]
pivot = pivot[["full_corpus", "nicad_eligible_LOC>=10"]]

fig, ax = plt.subplots(figsize=(6.5, 4))

principles = pivot.index.tolist()
x = np.arange(len(principles))
width = 0.36

bars_full = ax.bar(x - width/2, pivot["full_corpus"].values,
                   width=width, label="Full corpus (n=92,384)",
                   color="#bbbbbb", edgecolor="black", linewidth=0.4)
bars_elig = ax.bar(x + width/2, pivot["nicad_eligible_LOC>=10"].values,
                   width=width, label="NiCad-eligible (LOC ≥ 10, n=22,217)",
                   color="#2E6B8A", edgecolor="black", linewidth=0.4)

for bars in (bars_full, bars_elig):
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2,
                h + (0.005 if h >= 0 else -0.012),
                f"{h:+.3f}",
                ha="center", va="bottom" if h >= 0 else "top",
                fontsize=7, fontweight="bold")

ax.axhline(0, color="black", linewidth=0.7)
ax.axhline(0.10, color="grey", linestyle=":", linewidth=0.6, alpha=0.7)
ax.axhline(-0.10, color="grey", linestyle=":", linewidth=0.6, alpha=0.7)
ax.axhspan(-0.10, 0.10, color="lightgrey", alpha=0.20)

ax.set_xticks(x)
ax.set_xticklabels(principles, fontweight="bold")
ax.set_ylabel(r"Rank-biserial correlation ($r_{rb}$)")
ax.set_ylim(-0.22, 0.18)
ax.set_title("NiCad-eligible subset analysis: DIP effect vanishes, OCP wrong-direction strengthens",
             fontweight="bold", pad=8)
ax.legend(loc="upper right", framealpha=0.95)
ax.grid(axis="y", alpha=0.25)

plt.tight_layout()
plt.savefig("Results/figures/nicad_eligible.pdf")
plt.savefig("Results/figures/nicad_eligible.png", dpi=300)
print("Wrote: Results/figures/nicad_eligible.{pdf,png}")