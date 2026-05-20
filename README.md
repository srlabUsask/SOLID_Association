# Replication Package — *On the Relationship Between Method-Level SOLID Structural Signals and Code Clone Participation*

This replication package supports the empirical study investigating whether method-level adherence to three SOLID design principles — Single Responsibility (SRP), Open/Closed (OCP), and Dependency Inversion (DIP) — is associated with clone participation in eight mature open-source Java systems.

**Systems studied (92,415 methods with definitive clone labels; 15,892 cloned, 17.2%):**
Commons Lang, FitNesse, Hibernate ORM, Jackson Databind, JMeter, JUnit 5, Selenium, Struts.

The repository contains the analysis pipeline, derived results tables, publication figures, and the human-validation toolkit. The bulky raw artifacts that drive the pipeline (full NiCad clone-detection output, TXL-extracted Java method bodies, raw per-method LLM evaluation JSONs, and the two largest derived CSV tables) are archived in a companion Zenodo deposit (see next section).

---

## Companion Zenodo Deposit

The following artifacts are archived on Zenodo rather than committed here, due to file size.

> **Zenodo DOI:** [10.5281/zenodo.20298349](https://doi.org/10.5281/zenodo.20298349)

Files in the Zenodo deposit:

| Archive path | Size | Purpose |
|--------------|------|---------|
| `Clones/` | ~706 MB | Full raw NiCad v6.2 clone-detection output (XML + source-annotated HTML) |
| `Extracted_functions/*.xml` | ~82 MB | TXL-extracted Java method bodies (one file per project, input to the LLM evaluator) |
| `Evaluated_Solid_Scores_Jsons/*.json` | ~154 MB | Per-method LLM SOLID evaluation outputs (model / prompt / decoding metadata per record) |
| `corpus.csv` | ~72 MB | Validation-annotation corpus (rater pool sampled from this) |
| `Results/per_method_scores.csv` | ~30 MB | All methods × SOLID scores (Step 2 output) — needed by Steps 3–5 |
| `Results/inferential_corpus.csv` | ~36 MB | Joined corpus used by Steps 4–5 |

To reproduce the analysis from scratch, download the Zenodo deposit and copy each file/folder into its corresponding location in the cloned GitHub repository (paths in the table above are relative to the repository root).

---

## Repository Structure (what ships on GitHub)

```
.
├── README.md
│
├── Scripts/                             ← Analysis pipeline + LLM evaluator
│   ├── parse_nicad_xml.py                   Step 1: NiCad XML → clone-membership CSVs
│   ├── aggregate_solid_scores.py            Step 2: per-method JSONs → per_method_scores.csv
│   ├── build_inferential_corpus.py          Step 3: build inferential corpus (clones ⨝ scores ⨝ covariates)
│   ├── analysis_rq1.py                      Step 4: RQ1 (Mann-Whitney, rank-biserial, Cohen's d)
│   ├── regression_rq2.py                    Step 5: RQ2 (logistic regression, per-project + pooled)
│   ├── analysis_bootstrap_ci.py             Bootstrap confidence intervals
│   ├── analysis_disattenuation.py           Reliability disattenuation
│   ├── analysis_fdr.py                      Benjamini–Hochberg multiple-comparison correction
│   ├── analysis_interaction.py              SOLID × project interaction tests
│   ├── analysis_loo.py                      Leave-one-project-out sensitivity
│   ├── analysis_nicad_eligible.py           NiCad-eligible subgroup analysis
│   ├── analysis_ocp_branching.py            OCP mechanism: branching analysis
│   ├── analysis_ocp_clone_type.py           OCP × clone-type (T1/T2/T3) interaction
│   ├── analysis_score_distributions.py      Score-distribution summaries
│   ├── analysis_size_stratified.py          Size-stratified analysis
│   ├── compute_kappa_trajectory.py          Inter-rater κ across annotation rounds
│   ├── sample_ocp_mechanism.py              Stratified sampler for OCP mechanism review
│   ├── solid_from_xml.py                    LLM-based SOLID evaluator (re-run optional)
│   └── viz_*.py                             Publication figures (forest, MW dotplot, LOO, κ, size, etc.)
│
├── NicadClassXML/                       ← NiCad v6.2 class-level XML (input to Step 1)
│   └── <project>_functions-{blind-clones-0.00, blind-clones-0.30, clones-0.00}-classes.xml
│                                             T1 = exact clones, renaming disabled
│                                             T2 = blind-renamed exact clones
│                                             T3 = blind-renamed near-miss clones (30% dissimilarity)
│
├── validation_toolkit/                  ← Human-annotation workflow
│   ├── readme.md                            Toolkit workflow documentation
│   ├── annotate.py                          Flask annotation app
│   ├── build_corpus.py                      Build annotation corpus
│   ├── sample_holdout.py                    Stratified holdout sampler
│   ├── make_session_worksheet.py            Calibration-session worksheet generator
│   ├── make_reannotation_subset.py          Round-2 disagreement sampler
│   ├── reconcile_extreme_resolutions.py     Reconcile extreme-disagreement rulings
│   ├── analyze_agreement.py                 Cohen's κ + confusion matrices
│   ├── analyze_final.py                     Final reconciled-agreement statistics
│   ├── analyze_round3_dip.py                Round-3 DIP-specific analysis
│   ├── annotations_{rater_a,rater_b,merged}.db  Round-1 per-rater + reconciled SQLite DBs
│   ├── round2_{rater_a,rater_b}.db              Round-2 per-rater DBs
│   ├── round3_{rater_a,rater_b}.db              Round-3 per-rater DBs
│   ├── round3_dip_audit.csv                 Round-3 DIP audit table
│   ├── round3_dip_results.json              Round-3 DIP summary statistics
│   ├── Calibration Session Worksheet*.html  Rendered calibration worksheets
│   └── dip_clarification.html               DIP rubric clarification handout
│
└── Results/                             ← Pre-computed analysis outputs (regenerable from Steps 1–5)
    ├── ALL_PROJECTS_clone_methods.csv       All clone-labelled methods (Step 1 output)
    ├── <project>_clone_methods.csv          Per-project clone-method tables (×8)
    ├── batch_summary.csv                    Per-project clone counts
    ├── project_summary.csv                  Per-project SOLID summaries
    ├── score_distributions.csv              SOLID score frequency distributions
    ├── kappa_trajectory.csv                 Inter-rater κ per annotation round
    ├── bootstrap_ci.csv                     Bootstrap CIs for headline effects
    ├── multiple_comparison_results.csv      BH-FDR-corrected p-values
    ├── interaction_results.csv              SOLID × project interaction tests
    ├── nicad_eligible_results.csv           NiCad-eligible subgroup analysis
    ├── disattenuation_output.txt            Reliability disattenuation results
    ├── ocp_mechanism_sample.csv             Stratified sample for OCP mechanism inspection
    ├── rq1_analysis/                        RQ1 outputs (Mann-Whitney, effect sizes, per-project)
    ├── pooled/                              Pooled RQ2 logistic regression
    ├── <project>/                           Per-project RQ2 outputs (×8)
    ├── loo_<project>/, loo_summary/         Leave-one-project-out sensitivity
    ├── size_stratified/                     Size-stratified RQ2 outputs
    ├── ocp_clone_type/                      OCP × clone-type analysis
    └── figures/                             Publication figures (PDF + PNG)

<validation-workflow outputs at repository root>
holdout_sample.csv, holdout_manifest.json,
training_sample.csv, training_manifest.json, training.db,
rubric.html, calibration_worksheet.html,
agreement_summary.json, confusion_matrices.csv,
final_agreement_summary.json, final_confusion_matrices.csv,
disagreements_to_resolve.csv, extreme_cases_for_session.csv,
extreme_resolutions.csv, extreme_resolutions_raw.csv,
reannotation_round2.csv, reconciliation_report.txt,
results.csv, per_method_final_scores.csv
```

The files at the repository root document the human-annotation calibration and reconciliation rounds. `per_method_final_scores.csv` is the reconciled per-method label table; `agreement_summary.json` / `final_agreement_summary.json` report Cohen's κ across rounds; `extreme_resolutions.csv` records adjudicated extreme-disagreement decisions. They are reproduced by the scripts under `validation_toolkit/`.

The following paths exist in the analysis pipeline but are **not** committed to this GitHub repository — they live in the companion Zenodo deposit (see previous section): `Clones/`, `Extracted_functions/`, `Evaluated_Solid_Scores_Jsons/`, `corpus.csv`, `Results/per_method_scores.csv`, `Results/inferential_corpus.csv`.

---

## Requirements

**Python:** 3.11

| Package | Version tested |
|---------|----------------|
| pandas | 3.0.1 |
| numpy | 2.4.2 |
| scipy | 1.17.1 |
| statsmodels | 0.14.6 |
| matplotlib | 3.10.8 |

Optional, only for `validation_toolkit/annotate.py`: `flask` (any recent 3.x).

Optional, only for re-running `Scripts/solid_from_xml.py`: `openai` (with a valid `OPENAI_API_KEY` set in the environment).

Install with conda:
```bash
conda create -n solid python=3.11
conda activate solid
pip install pandas==3.0.1 numpy==2.4.2 scipy==1.17.1 statsmodels==0.14.6 matplotlib==3.10.8
```

Or with pip directly:
```bash
pip install pandas numpy scipy statsmodels matplotlib
```

---

## Reproduction Steps

All commands are run from the repository root. Expected total runtime (after fetching the Zenodo deposit): ~5–10 minutes on a modern laptop. Pre-computed analysis outputs are already present under `Results/` so every reported finding can be verified without re-running the pipeline.

Before running Steps 2–5, fetch the companion Zenodo deposit and place the six paths listed in the previous section into their corresponding locations in your cloned working copy. Step 1 can be run from `NicadClassXML/` (committed here) alone.

---

### Step 1 — Parse NiCad clone XML outputs

```bash
python Scripts/parse_nicad_xml.py \
  --batch_dir NicadClassXML/ \
  --output_dir Results/
```

Reads each `*-classes.xml` in `NicadClassXML/`, extracts clone membership, and writes per-project `*_clone_methods.csv` files plus `Results/ALL_PROJECTS_clone_methods.csv`.

---

### Step 2 — Aggregate SOLID evaluation scores

Requires `Evaluated_Solid_Scores_Jsons/` from the Zenodo deposit.

```bash
python Scripts/aggregate_solid_scores.py \
  --data_dir Evaluated_Solid_Scores_Jsons/ \
  --output_dir Results/
```

Reads the eight `*_SOLID_Eval.json` files and produces `Results/per_method_scores.csv` with columns `project, file, startline, endline, srp, ocp, dip, composite`.

---

### Step 3 — Build the inferential corpus

Requires `Results/per_method_scores.csv` (either from Step 2 or from the Zenodo deposit).

```bash
python Scripts/build_inferential_corpus.py \
  --method_csv Results/per_method_scores.csv \
  --clone_csv  Results/ALL_PROJECTS_clone_methods.csv \
  --output     Results/inferential_corpus.csv
```

Joins SOLID scores to clone labels on `(project, normalised_path, startline)` and attaches covariates (method LOC, NiCad eligibility flags). The output is the unit of analysis for Steps 4–5.

---

### Step 4 — RQ1 analysis

```bash
python Scripts/analysis_rq1.py \
  --method_csv Results/per_method_scores.csv \
  --clone_csv  Results/ALL_PROJECTS_clone_methods.csv \
  --output_dir Results/rq1_analysis/
```

Runs Mann-Whitney U tests, rank-biserial correlation, and Cohen's d for each principle, overall and per project. Produces `rq1_summary.txt`, `method_level_summary.csv`, `per_project_method_comparison.csv`, `system_level_summary.csv`, and `clone_type_distributions.csv`.

---

### Step 5 — RQ2 analysis

```bash
python Scripts/regression_rq2.py \
  --method_csv Results/per_method_scores.csv \
  --clone_csv  Results/ALL_PROJECTS_clone_methods.csv \
  --output_dir Results/
```

Fits per-project and pooled logistic-regression models with project fixed effects and cluster-robust standard errors on the 92,415 methods within the analysable `/src/` corpus with definitive clone labels. Per-project outputs land in `Results/<project>/`; the pooled model lands in `Results/pooled/`.

---

### Robustness and sensitivity analyses

The remaining `Scripts/analysis_*.py` files reproduce the supplementary analyses reported in the paper:

| Script | Output |
|--------|--------|
| `analysis_bootstrap_ci.py` | `Results/bootstrap_ci.csv` |
| `analysis_disattenuation.py` | `Results/disattenuation_output.txt` |
| `analysis_fdr.py` | `Results/multiple_comparison_results.csv` |
| `analysis_interaction.py` | `Results/interaction_results.csv` |
| `analysis_loo.py` | `Results/loo_<project>/`, `Results/loo_summary/` |
| `analysis_nicad_eligible.py` | `Results/nicad_eligible_results.csv` |
| `analysis_ocp_branching.py` | columns added to `Results/inferential_corpus.csv` |
| `analysis_ocp_clone_type.py` | `Results/ocp_clone_type/` |
| `analysis_score_distributions.py` | `Results/score_distributions.csv` |
| `analysis_size_stratified.py` | `Results/size_stratified/` |
| `compute_kappa_trajectory.py` | `Results/kappa_trajectory.csv` |
| `sample_ocp_mechanism.py` | `Results/ocp_mechanism_sample.csv` |

Each reads `Results/inferential_corpus.csv` or `Results/per_method_scores.csv` as input.

The `Scripts/viz_*.py` scripts regenerate every figure under `Results/figures/` from those outputs:

| Script | Figure |
|--------|--------|
| `viz_forest_plot.py` | `forest_plot.{pdf,png}` |
| `viz_mw_dotplot.py` | `mw_dotplot.{pdf,png}` |
| `viz_kappa_trajectory.py` | `kappa_trajectory.{pdf,png}` |
| `viz_loo.py` | `loo.{pdf,png}` |
| `viz_nicad_eligible.py` | `nicad_eligible.{pdf,png}` |
| `viz_score_distributions.py` | `score_distributions.{pdf,png}` |
| `viz_size_stratified.py` | `size_stratified.{pdf,png}` |

---

### SOLID evaluation via LLM (optional, regenerates the Zenodo `Evaluated_Solid_Scores_Jsons/`)

This step is pre-computed; the outputs are provided in the Zenodo deposit. The instructions below describe how to regenerate the per-method JSONs from the TXL-extracted method bodies.

Requires `Extracted_functions/` from the Zenodo deposit.

```bash
python Scripts/solid_from_xml.py \
  --input  Extracted_functions/<project>_functions.xml \
  --output Evaluated_Solid_Scores_Jsons/<project>_SOLID_Eval.json \
  --model  gpt-5.2
```

Each Java method body (extracted from source with TXL) is evaluated against the SRP, OCP, and DIP rubrics. Scores are integers ∈ {0, 1, 2} per principle (0 = violation, 2 = fully compliant). The exact model identifier and decoding configuration are archived in the script and in every JSON record. Requires a valid `OPENAI_API_KEY` environment variable.

**Evaluation prompt (`EVAL_PROMPT_V1`, verbatim):**

<details>
<summary>Click to expand prompt</summary>

```
You are a senior software architecture researcher scoring METHOD-LEVEL structural signals related to SRP, OCP, and DIP in Java.

IMPORTANT:
- Output VALID JSON only.
- No markdown.
- No commentary outside JSON.
- Be conservative. If the method alone is insufficient, set score=1 and add flag "needs_more_context".
- You are NOT inferring intent or domain meaning. You are scoring observable structural signals only.

You are evaluating a SINGLE Java method extracted from a larger system.
Identifiers may have been consistently renamed (e.g., x1, x2). Do NOT infer semantics from names.

---------------------------------------
SCORING RUBRIC (Method-Level Signals)
---------------------------------------

Score per principle:
0 = Violated (clear structural evidence)
1 = Partial / Uncertain (mixed signals OR insufficient context)
2 = Compliant (clear structural evidence)

You MUST include 1-3 evidence items per principle.
Each evidence item MUST cite a concrete construct and include a short quoted snippet from the method (or a very precise description if quoting is impossible).

Principles:

1) SRP — Single Responsibility (method cohesion)
Score whether the method does one cohesive responsibility.

Score=0 if:
- Multiple distinct responsibilities are present (e.g., validates + persists + logs), OR
- Unrelated side effects are mixed (e.g., updates state + UI + IO).

Score=2 if:
- One focused responsibility, OR
- It delegates via at most 3 calls and contains no independent logic beyond delegation sequencing (thin orchestrator).

Score=1 + flag "needs_more_context" if:
- SRP judgement depends on class-level role or broader workflow not visible here.

---

2) OCP — Extension vs. modification RISK SIGNALS (method-level proxy)
You are NOT declaring true OCP compliance for the system. You are scoring whether this method structurally encodes variation such that future requirements likely require modifying THIS method.

Score=0 if:
- if/else or switch chain with 3+ branches encoding behavioral variants, OR
- Hard-coded policy thresholds / magic constants that appear to represent changeable policy, OR
- Repeated copy-modify style branches.

Score=2 if:
- Behavior is delegated to collaborators / polymorphic calls, and branching is minimal (0-2 branches) and not encoding variants.

Score=1 + flag "needs_more_context" if:
- You cannot see whether delegation is polymorphic/strategy-based, OR
- Branching exists but could be simple control flow without representing an extensibility point.

---

3) DIP — Dependency Inversion (replaceable dependency signals)
Score whether the method introduces tight coupling to replaceable concrete collaborators.

Score=0 if:
- Instantiates a likely replaceable collaborator/service (e.g., repository, network client, UI subsystem, persistence service) directly inside the method, OR
- Uses static singletons/globals for replaceable collaborators, OR
- Strong framework coupling that acts as a direct dependency (not just DTOs/events).

IMPORTANT: The following are NOT DIP violations:
- Instantiating collections (ArrayList/HashMap/etc.), strings, primitives, simple data/value objects, iterators/enumerators
- Creating Exceptions
- Creating small helper objects local to the method, when not a replaceable external collaborator

Score=2 if:
- Dependencies are injected via parameters/fields (as abstractions), OR
- No replaceable dependencies appear in the method.

Score=1 + flag "needs_more_context" if:
- A 'new X(...)' appears, but you cannot determine if X is a replaceable collaborator vs a value/helper type.

---------------------------------------
OUTPUT FORMAT (STRICT JSON)
---------------------------------------
{
  "srp": {"score":0|1|2,"label":"Violated|Partial|Compliant","confidence":0.0-1.0,"evidence":["..."],"notes":""},
  "ocp": {"score":0|1|2,"label":"Violated|Partial|Compliant","confidence":0.0-1.0,"evidence":["..."],"notes":""},
  "dip": {"score":0|1|2,"label":"Violated|Partial|Compliant","confidence":0.0-1.0,"evidence":["..."],"notes":""},
  "overall": {"solid_score":0-6,"flags":[]}
}

Rules:
- Evidence must reference specific structural constructs and preferably quote a snippet.
- If insufficient context for SRP or OCP, include flag "needs_more_context".
- Do NOT invent missing hierarchy or intent.
- Confidence must reflect certainty.

METADATA:
id: {{id}}
file: {{file_path}}
startline: {{startline}}
endline: {{endline}}

METHOD CODE:
{{code}}

Evaluate now.
```

</details>

**Key prompt design decisions:**
- TXL-extracted methods are pre-processed with consistent identifier renaming; the prompt instructs the model to score structural signals only, not semantic intent.
- Temperature = 0.0 for deterministic output.
- Schema validation is enforced programmatically; malformed responses trigger a self-repair retry (up to 2 attempts).
- Methods exceeding 14,000 characters are truncated (head 9,000 + tail 3,000 chars) and flagged `truncated_input` in the output.

---

## Human Validation

`validation_toolkit/` contains everything needed to reproduce the human-annotation validation reported in the paper: a Flask-based two-rater annotation app, the stratified holdout sampler, calibration-session worksheet generator, and three rounds of agreement analysis (Cohen's κ, confusion matrices, extreme-case reconciliation). See `validation_toolkit/readme.md` for the end-to-end workflow.

The per-rater SQLite databases (`annotations_rater_a.db`, `annotations_rater_b.db`, `round2_*.db`, `round3_*.db`) and the reconciled DB (`annotations_merged.db`) are committed under `validation_toolkit/`. The calibration worksheets and per-round CSV/JSON outputs live at the repository root and are consumed by the toolkit scripts. The full annotation corpus (`corpus.csv`, ~72 MB) lives in the Zenodo deposit; download it to the repository root before running `sample_holdout.py` or `build_corpus.py`.

---

## Key Results (Pre-computed)

Pre-computed results are provided in `Results/` so all findings can be verified without re-running the full pipeline.

**RQ1 — Method-level effect sizes (N = 92,415):**

| Principle | r_rb | p |
|-----------|------|---|
| SRP | +0.022 | < 10⁻²¹ |
| OCP | −0.014 | < 10⁻⁷ |
| DIP | +0.140 | < 10⁻³⁰⁰ |

Sign convention: positive r_rb = cloned methods rank lower (worse compliance).
All effects are statistically significant but negligible to small in magnitude.

**RQ2 — Pooled logistic regression (N = 92,415):**

| Principle | OR | 95% CI | p |
|-----------|----|--------|---|
| SRP | 1.173 | [1.069, 1.287] | 0.0007 |
| OCP | 1.360 | [1.096, 1.688] | 0.005 |
| DIP | 0.806 | [0.691, 0.940] | 0.006 |
| MethodLOC | 1.860 | [1.435, 2.411] | < 0.001 |

Marginal McFadden R² = 0.020 (SOLID contribution over project FE + MethodLOC baseline).
Standard errors clustered by project. OR > 1 indicates higher scores are associated with higher clone odds; OR < 1 indicates a protective association.

---

## Data Sources

- **SOLID scores** were generated by applying an LLM-based rubric evaluator (`Scripts/solid_from_xml.py`) to each TXL-extracted method body. Scores ∈ {0, 1, 2} per principle (0 = violation detected, 2 = fully compliant); the prompt, model identifier, decoding settings, and per-record run metadata are recorded in the script and in every JSON record. Raw per-method JSON outputs are archived in the Zenodo deposit under `Evaluated_Solid_Scores_Jsons/`. The aggregated per-method score table (`Results/per_method_scores.csv`) is likewise on Zenodo because of its size.
- **Function extraction** was performed using TXL (a grammar-based source-transformation language) to parse each Java project and isolate individual method bodies. The resulting XML files are archived in the Zenodo deposit under `Extracted_functions/`. TXL can be downloaded from [txl.ca](https://www.txl.ca).
- **Clone detection** was performed with NiCad v6.2 at function granularity. The full NiCad output (including source-annotated HTML) is archived in the Zenodo deposit under `Clones/`; the class-level XML files consumed by the analysis pipeline are committed here under `NicadClassXML/`. Three clone types are detected: T1 (exact clones with renaming disabled), T2 (blind-renamed exact clones), T3 (blind-renamed near-miss clones with 30% dissimilarity threshold). NiCad v6.2 can be downloaded from [txl.ca](https://www.txl.ca).
- **Human-annotation data** was produced by `validation_toolkit/`. The per-rater SQLite databases and round-by-round derived outputs are committed in this repository; the upstream `corpus.csv` (annotation pool) is in the Zenodo deposit.
- Raw source code for the eight studied Java systems is **not redistributed**. All eight are publicly available open-source repositories.

---

## License

- All source code in `Scripts/` and `validation_toolkit/` is released under the **Apache License 2.0**.
- All data files (`Results/*.csv`, `NicadClassXML/`, and the validation outputs at the repository root, plus the artifacts in the companion Zenodo deposit) are released under the **Creative Commons Attribution 4.0 International (CC-BY-4.0)** license.

The eight studied Java systems retain their original upstream licenses and are not redistributed in this package.

---

## Citation

If you use this replication package, please cite the accompanying paper and the Zenodo companion artifacts deposit:

> Roy, P. R. (2026). *Companion artifacts for "On the Relationship Between Method-Level SOLID Structural Signals and Code Clone Participation"*. Zenodo. [https://doi.org/10.5281/zenodo.20298349](https://doi.org/10.5281/zenodo.20298349)

A `CITATION.cff` will be added with the final paper bibliographic record at camera-ready.
