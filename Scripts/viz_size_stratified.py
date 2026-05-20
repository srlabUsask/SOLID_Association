import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams.update({
    'font.size': 7, 'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.labelsize': 7, 'axes.titlesize': 8,
    'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'axes.linewidth': 0.5, 'savefig.dpi': 600,
    'savefig.bbox': 'tight', 'pdf.fonttype': 42, 'ps.fonttype': 42,
})

df = pd.read_csv("Results/size_stratified/size_stratified_results.csv")

BUCKETS = ["Q1 (tiny)", "Q2 (small)", "Q3 (medium)", "Q4 (large)"]
PRINCIPLES = ["SRP", "OCP", "DIP"]
POOLED = {"SRP": 0.022, "OCP": -0.014, "DIP": 0.140}

mat = df.pivot(index="size_bucket", columns="principle", values="r_rb")
mat = mat.reindex(BUCKETS)[PRINCIPLES]

pooled_row = pd.DataFrame([[POOLED[p] for p in PRINCIPLES]],
                          index=["Pooled (all sizes)"], columns=PRINCIPLES)
mat_full = pd.concat([mat, pooled_row])

fig, ax = plt.subplots(figsize=(5.5, 3.5))
vmax = 0.20
im = ax.imshow(mat_full.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")

row_labels = [
    "Q1 (LOC ≤ 3)",
    "Q2 (LOC = 4)",
    "Q3 (LOC 5–9)",
    "Q4 (LOC > 9)",
    "Pooled",
]

ax.set_xticks(range(len(PRINCIPLES)))
ax.set_xticklabels(PRINCIPLES, fontweight="bold")
ax.set_yticks(range(len(row_labels)))
ax.set_yticklabels(row_labels)

for i in range(mat_full.shape[0]):
    for j in range(mat_full.shape[1]):
        val = mat_full.iloc[i, j]
        text_color = "white" if abs(val) > 0.10 else "black"
        weight = "bold" if i < 4 else "normal"
        ax.text(j, i, f"{val:+.3f}", ha="center", va="center",
                color=text_color, fontsize=8, fontweight=weight)

ax.axhline(3.5, color="black", linewidth=1.0)

cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.ax.tick_params(labelsize=6)
cbar.set_label(r"$r_{rb}$ (positive: cloned ranks lower)",
               rotation=270, labelpad=14, fontsize=7)

ax.set_title("Size-stratified rank-biserial within method-LOC quartiles",
             fontweight="bold", pad=8)

plt.savefig("Results/figures/size_stratified.pdf")
plt.savefig("Results/figures/size_stratified.png", dpi=300)
print("Wrote: Results/figures/size_stratified.{pdf,png}")