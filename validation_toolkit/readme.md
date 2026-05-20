# Validation Toolkit

Scripts and supporting files for the held-out human-rater validation of the
LLM-based SOLID scoring pipeline. This toolkit draws a held-out sample from
the analytic corpus, supports blind two-rater annotation, and computes
inter-rater agreement and human-vs-LLM agreement statistics (raw agreement,
Cohen's kappa, linearly weighted kappa, per-class precision/recall/F1, 3x3
confusion matrices).

## Components

| File | Role |
|------|------|
| `build_corpus.py` | Builds a unified annotation corpus from the per-project `*_SOLID_Eval.json` (LLM scores) and `*_functions.xml` (method bodies). |
| `sample_holdout.py` | Draws a stratified random held-out sample (default n = 200) from the corpus, disjoint from the calibration set. |
| `annotate.py` | Local Flask app for blind annotation; persists per-rater scores to SQLite. |
| `analyze_agreement.py` | Round-1 agreement statistics: inter-rater agreement and LLM-vs-consensus agreement, with confusion matrices. |
| `make_session_worksheet.py` | Renders the disagreement-resolution worksheet used in the calibration session. |
| `make_reannotation_subset.py` | Builds the round-2 disagreement-only subset from round-1 outputs. |
| `reconcile_extreme_resolutions.py` | Applies session-resolved extreme-disagreement rulings to the consolidated annotations. |
| `analyze_final.py` | Final agreement analysis combining round-1, round-2, and extreme-resolution outputs. |
| `analyze_round3_dip.py` | DIP-only round-3 re-annotation analysis. |

## Inputs and outputs

The pipeline produces or consumes the following artifacts, located at the
repository root unless noted otherwise:

| Artifact | Producer | Consumer |
|----------|----------|----------|
| `corpus.csv` | `build_corpus.py` | `sample_holdout.py` |
| `holdout_sample.csv`, `holdout_manifest.json` | `sample_holdout.py` | `annotate.py`, downstream analyses |
| `validation_toolkit/annotations_rater_a.db`, `annotations_rater_b.db` | `annotate.py` | `analyze_agreement.py` |
| `results.csv` | `annotate.py --export` | `analyze_agreement.py` |
| `agreement_summary.json`, `confusion_matrices.csv`, `disagreements_to_resolve.csv` | `analyze_agreement.py` | `make_session_worksheet.py`, reconciliation |
| `extreme_resolutions.csv` | manual session output | `reconcile_extreme_resolutions.py` |
| `validation_toolkit/round2_rater_a.db`, `round2_rater_b.db` | `annotate.py` (round 2) | `analyze_final.py` |
| `final_agreement_summary.json`, `final_confusion_matrices.csv`, `per_method_final_scores.csv` | `analyze_final.py` | paper tables |
| `validation_toolkit/round3_rater_a.db`, `round3_rater_b.db` | `annotate.py` (round 3) | `analyze_round3_dip.py` |
| `validation_toolkit/round3_dip_audit.csv`, `round3_dip_results.json` | `analyze_round3_dip.py` | paper tables |

## Workflow

### 1. Build the unified corpus

```bash
python validation_toolkit/build_corpus.py \
    --root . \
    --output corpus.csv
```

Joins LLM scores and source bodies on `(file_path, startline, endline)` and
writes one row per method. The output corpus matches the analytic corpus
size reported in the paper (92,415 methods).

### 2. Draw the held-out sample

```bash
python validation_toolkit/sample_holdout.py \
    --corpus corpus.csv \
    --exclude-ids calibration_ids.txt \
    --output holdout_sample.csv \
    --manifest holdout_manifest.json \
    --n 200 \
    --seed 42 \
    --loc-floor 3
```

Sampling parameters:

- `--n 200`: sample size.
- `--seed 42`: deterministic sample for reproducibility.
- `--loc-floor 3`: excludes methods with fewer than three lines of code
  from the eligible pool (empty bodies and one-line accessors).
- `--exclude-ids calibration_ids.txt`: a text file with one calibration-set
  method ID per line. The IDs must match the `id` field of the JSON
  records (e.g., `systems/Projects/junit5-main/Foo.java:22-24`).

The sample is stratified in two phases: half drawn proportional to the
joint distribution of LLM scores across SRP, OCP, and DIP, and half
oversampled from cells where any principle was scored 0 or 1.

### 3. Run the annotation app

Install dependencies:

```bash
pip install flask pandas scikit-learn
```

Start the app:

```bash
python validation_toolkit/annotate.py \
    --sample holdout_sample.csv \
    --db validation_toolkit/annotations.db \
    --rubric rubric.html
```

Open `http://localhost:5000` in a browser. Each rater authenticates with
their identifier (`annotator_a`, `annotator_b`). The LLM verdict is hidden
during scoring. SQLite preserves progress across sessions.

### 4. Export and analyse round-1 annotations

```bash
python validation_toolkit/annotate.py \
    --sample holdout_sample.csv \
    --db validation_toolkit/annotations.db \
    --export results.csv

python validation_toolkit/analyze_agreement.py \
    --results results.csv \
    --output agreement_summary.json \
    --confusion confusion_matrices.csv \
    --disagreements disagreements_to_resolve.csv
```

`disagreements_to_resolve.csv` enumerates `(method_id, principle)` pairs
with rater disagreement or an N/A marking.

### 5. Calibration session and extreme-disagreement resolution

`make_session_worksheet.py` renders an HTML worksheet covering extreme
disagreements (score deltas of 2). The session output is recorded in
`extreme_resolutions.csv`, which is applied via
`reconcile_extreme_resolutions.py` to produce the consolidated round-1
labels.

### 6. Round-2 reannotation

`make_reannotation_subset.py` constructs `reannotation_round2.csv` from
the unresolved round-1 disagreements. Round-2 annotation uses the same
Flask app against separate per-rater databases (`round2_rater_a.db`,
`round2_rater_b.db`).

### 7. Final reconciled agreement

```bash
python validation_toolkit/analyze_final.py \
    --round1 results.csv \
    --round2-rater-a validation_toolkit/round2_rater_a.db \
    --round2-rater-b validation_toolkit/round2_rater_b.db \
    --extreme extreme_resolutions.csv \
    --sample holdout_sample.csv \
    --output final_agreement_summary.json \
    --confusion final_confusion_matrices.csv \
    --audit per_method_final_scores.csv
```

Combines round-1, round-2, and extreme-resolution outputs into the final
per-method consensus labels and agreement statistics.

### 8. Round-3 DIP reannotation

DIP underwent a third reannotation round following a rubric clarification
documented in `validation_toolkit/dip_clarification.html`. The round-3
analysis is performed by `analyze_round3_dip.py`:

```bash
python validation_toolkit/analyze_round3_dip.py \
    --round3-rater-a validation_toolkit/round3_rater_a.db \
    --round3-rater-b validation_toolkit/round3_rater_b.db \
    --sample holdout_sample.csv \
    --extreme extreme_resolutions.csv \
    --output round3_dip_results.json \
    --audit round3_dip_audit.csv
```

## Replication

The following inputs and outputs are required for replication and are
committed in this repository at the locations indicated above:

- Scripts under `validation_toolkit/`
- Per-rater and reconciled SQLite databases under `validation_toolkit/`
  (`annotations_rater_a.db`, `annotations_rater_b.db`,
  `annotations_merged.db`, `round2_*.db`, `round3_*.db`)
- Round-by-round CSV / JSON outputs at the repository root
- The rubric file (`rubric.html`) and calibration worksheets
  (`calibration_worksheet.html`, `validation_toolkit/Calibration Session
  Worksheet*.html`, `validation_toolkit/dip_clarification.html`)

The full annotation corpus (`corpus.csv`, ~72 MB) is archived in the
companion Zenodo deposit referenced from the top-level `README.md`.
