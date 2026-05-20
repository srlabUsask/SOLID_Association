"""
analysis_disattenuation.py

Errors-in-variables correction for DIP-related effect sizes given measurement
reliability (κ). Reports disattenuated rank-biserial under varying reliability
assumptions for pooled RQ1 and within-Q4 RQ2 effects.

Classical attenuation formula (Spearman, 1904):
    r_true ≈ r_observed / sqrt(reliability_X * reliability_Y)

With clone label as binary ground-truth (reliability ≈ 1) and DIP as the
noisy predictor:
    r_disattenuated ≈ r_observed / sqrt(reliability_DIP)
"""

import math

# Observed effects from the analysis
EFFECTS = {
    "RQ1 pooled DIP":     {"r_observed": +0.140, "n": 92_415},
    "RQ2 Q4 DIP":         {"r_observed": +0.018, "n": 22_217},
    "RQ2 Q1 DIP":         {"r_observed": +0.184, "n": 24_891},
    "Struts DIP":         {"r_observed": +0.401, "n": 14_618},
    "Hibernate DIP":      {"r_observed": +0.033, "n": 16_404},
}

# Reliability scenarios:
# kappa_round1: Round 1 baseline (no rubric refinement)
# kappa_round3: Round 3 (post-calibration, post-rubric-clarification)
# kappa_optimistic: hypothetical upper bound for robustness check
SCENARIOS = {
    "kappa_round1 = 0.31": 0.31,
    "kappa_round3 = 0.20": 0.20,
    "kappa_optimistic = 0.50": 0.50,
}

def disattenuate(r_observed: float, reliability: float) -> float:
    """Classical correction for attenuation due to measurement error."""
    if reliability <= 0:
        return float("nan")
    return r_observed / math.sqrt(reliability)

# Print formatted table
print(f"{'Effect':<25} {'r_observed':>12} {'Scenario':<25} {'r_corrected':>12}")
print("-" * 76)
for effect_name, data in EFFECTS.items():
    for scenario_name, reliability in SCENARIOS.items():
        r_corr = disattenuate(data["r_observed"], reliability)
        print(f"{effect_name:<25} {data['r_observed']:>+12.3f} "
              f"{scenario_name:<25} {r_corr:>+12.3f}")
    print()

# Key interpretation: does the Q4 attenuation pattern survive disattenuation?
print("\n" + "=" * 76)
print("Q4 attenuation check (RQ1 pooled vs RQ2 Q4, disattenuated):")
print("=" * 76)
for scenario_name, reliability in SCENARIOS.items():
    r_pooled_corr = disattenuate(EFFECTS["RQ1 pooled DIP"]["r_observed"], reliability)
    r_q4_corr = disattenuate(EFFECTS["RQ2 Q4 DIP"]["r_observed"], reliability)
    delta = r_pooled_corr - r_q4_corr
    print(f"{scenario_name:<25}  pooled={r_pooled_corr:+.3f}  Q4={r_q4_corr:+.3f}  Δ={delta:+.3f}")