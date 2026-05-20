import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams.update({
    'font.size': 7, 'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.labelsize': 7, 'axes.titlesize': 8,
    'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'legend.fontsize': 6, 'axes.linewidth': 0.5,
    'lines.linewidth': 1.2, 'savefig.dpi': 600,
    'savefig.bbox': 'tight', 'pdf.fonttype': 42, 'ps.fonttype': 42,
})

COL = {"SRP": "#B5651D", "OCP": "#2E6B8A", "DIP": "#C0392B"}
MARKERS = {"SRP": "o", "OCP": "s", "DIP": "^"}
ROUND_LABEL = {
    "round1": "Round 1\n(initial)",
    "round2": "Round 2\n(post-calibration)",
    "round3": "Round 3\n(post-clarification)",
}
ROUND_ORDER = ["round1", "round2", "round3"]

df = pd.read_csv("Results/kappa_trajectory.csv")

fig, ax = plt.subplots(figsize=(7, 4.2))

# SRP and OCP: locked at round 1 only (single points)
for principle in ["SRP", "OCP"]:
    sub = df[(df["principle"] == principle) & (df["round"] == "round1")]
    if len(sub) == 0 or pd.isna(sub["weighted_kappa"].iloc[0]):
        continue
    k = sub["weighted_kappa"].iloc[0]
    n = int(sub["n"].iloc[0])
    ax.plot(0, k, marker=MARKERS[principle], markersize=11,
            color=COL[principle],
            label=f"{principle} (locked at round 1, n={n})",
            markeredgecolor="black", markeredgewidth=0.6, linestyle="")
    ax.annotate(f"{k:.2f}", (0, k), textcoords="offset points",
                xytext=(10, 4), fontsize=8,
                color=COL[principle], fontweight="bold")

# DIP: full three-round trajectory
dip = df[df["principle"] == "DIP"].dropna(subset=["weighted_kappa"]).copy()
dip = dip.set_index("round").reindex(ROUND_ORDER).reset_index()
dip = dip.dropna(subset=["weighted_kappa"])
xs = [ROUND_ORDER.index(r) for r in dip["round"]]
ys = dip["weighted_kappa"].tolist()
ns = [int(v) for v in dip["n"].tolist()]
ax.plot(xs, ys, marker=MARKERS["DIP"], markersize=9,
        color=COL["DIP"],
        label="DIP (re-attempted across three rounds)",
        markeredgecolor="black", markeredgewidth=0.5)
for xi, yi, ni in zip(xs, ys, ns):
    ax.annotate(f"{yi:.2f}", (xi, yi), textcoords="offset points",
                xytext=(8, 6), fontsize=8,
                color=COL["DIP"], fontweight="bold")

# Reference thresholds
ax.axhline(0.61, color="#27AE60", linestyle=":", linewidth=0.8, alpha=0.8,
           label="Substantial agreement (κ = 0.61)")
ax.axhline(0.41, color="#7F8C8D", linestyle=":", linewidth=0.8, alpha=0.8,
           label="Moderate agreement (κ = 0.41)")
ax.axhline(0.50, color="black", linestyle="--", linewidth=0.9,
           label="Pre-committed DIP threshold (κ = 0.50)")
ax.axhline(0.0, color="black", linewidth=0.5)

# Shade the "unreliable" zone
ax.axhspan(-0.10, 0.41, color="red", alpha=0.04)

ax.set_xticks(range(len(ROUND_ORDER)))
ax.set_xticklabels([ROUND_LABEL[r] for r in ROUND_ORDER])
ax.set_ylabel("Weighted Cohen's κ (inter-rater)")
ax.set_xlabel("Annotation round")
ax.set_ylim(-0.15, 0.80)
ax.set_title("Inter-rater κ: SRP and OCP locked at round 1; "
             "DIP fails to converge across three rounds",
             fontweight="bold", pad=8)
ax.legend(loc="upper right", framealpha=0.95, ncol=1, fontsize=6)
ax.grid(True, alpha=0.25)

plt.savefig("Results/figures/kappa_trajectory.pdf")
plt.savefig("Results/figures/kappa_trajectory.png", dpi=300)
print("Wrote: Results/figures/kappa_trajectory.{pdf,png}")