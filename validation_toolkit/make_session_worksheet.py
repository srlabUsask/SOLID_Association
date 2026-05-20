"""
make_session_worksheet.py
-------------------------
Generates a single self-contained HTML worksheet for the calibration
session. Includes every extreme-disagreement case (rater A scored 0,
rater B scored 2, or vice versa) with full method source, both rater
scores, the relevant rubric criterion, and space to record the agreed
score plus a one-line rationale.

The HTML is print-friendly (page breaks between cases) and can be
opened in any browser. Students and PI walk through it together.

Inputs:
    - extreme_cases.csv (from the 0_vs_2 boundary diagnostic)
    - holdout_sample.csv (for method source code and metadata)

Output:
    - calibration_worksheet.html

Usage:
    python make_session_worksheet.py \\
        --extreme ../extreme_cases_for_session.csv \\
        --sample ../holdout_sample.csv \\
        --output ../calibration_worksheet.html
"""

import argparse
import json
from html import escape
from pathlib import Path

import pandas as pd


# Compact rubric criteria (printed alongside each case so the discussion
# can reference exact wording without flipping back to the full rubric).
RUBRIC_SUMMARY = {
    "srp": {
        "0": "Multiple distinct responsibilities OR unrelated side effects mixed.",
        "1": "Cannot tell from method alone (depends on class-level role).",
        "2": "One focused responsibility OR thin orchestrator (≤3 delegated calls).",
    },
    "ocp": {
        "0": "if/else or switch chain with 3+ branches encoding variants, OR hard-coded policy thresholds, OR copy-modify branches.",
        "1": "Branching exists but unclear if it represents an extensibility point.",
        "2": "Behavior delegated to collaborators; branching minimal (0–2) and not encoding variants.",
    },
    "dip": {
        "0": "Instantiates replaceable collaborator/service directly, OR uses static singletons for replaceable collaborators, OR strong framework coupling.",
        "1": "new X(...) appears but unclear if X is replaceable collaborator vs value/helper.",
        "2": "Dependencies injected via parameters/fields, OR no replaceable dependencies appear.",
    },
}

NOT_DIP_VIOLATIONS = (
    "<strong>NOT DIP violations:</strong> instantiating collections "
    "(ArrayList, HashMap), strings, primitives, value objects, "
    "iterators, exceptions, or small local helpers."
)


HTML_HEAD = """<!doctype html>
<html><head><meta charset="utf-8"><title>Calibration Session Worksheet</title>
<style>
  @media print {
    .case { page-break-after: always; }
    .header { page-break-after: always; }
  }
  body { font-family: -apple-system, system-ui, "Segoe UI", sans-serif; max-width: 900px; margin: 20px auto; padding: 0 30px; color: #222; line-height: 1.5; }
  h1 { font-size: 22px; }
  h2 { font-size: 18px; border-bottom: 2px solid #2469d4; padding-bottom: 4px; }
  h3 { font-size: 15px; margin-bottom: 4px; }
  .header { background: #fafafa; border: 1px solid #ddd; padding: 16px 20px; border-radius: 6px; margin-bottom: 24px; }
  .case { border: 1px solid #ccc; border-radius: 6px; padding: 16px 20px; margin-bottom: 28px; background: white; }
  .case-meta { font-size: 12px; color: #555; margin-bottom: 6px; }
  .case-meta code { background: #f0f0f0; padding: 1px 5px; border-radius: 3px; word-break: break-all; }
  pre.code { background: #1e1e1e; color: #e8e8e8; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 12.5px; line-height: 1.45; max-height: 380px; }
  .scores { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 10px 0; padding: 10px; background: #fff8e1; border-left: 3px solid #d4a017; }
  .scores div { font-size: 13px; }
  .rubric-box { background: #f4f7fb; border-left: 3px solid #2469d4; padding: 10px 14px; margin: 10px 0; font-size: 13px; }
  .rubric-box ul { margin: 4px 0 0 18px; padding: 0; }
  .rubric-box li { margin-bottom: 3px; }
  .decision { background: #f0fff0; border: 1px dashed #4a9; padding: 12px 16px; margin-top: 12px; }
  .decision label { display: block; margin: 6px 0 2px; font-weight: 600; font-size: 13px; }
  .decision input[type=text], .decision textarea { width: 100%; box-sizing: border-box; padding: 6px; font-family: inherit; font-size: 13px; border: 1px solid #aaa; border-radius: 3px; }
  .checkbox-row { display: flex; gap: 16px; align-items: center; }
  .checkbox-row label { font-weight: 400; font-size: 13px; }
  .session-info { font-size: 13px; color: #444; }
</style>
</head>
<body>
"""


def render_header(n_cases: int, by_principle: dict) -> str:
    rows = "".join(
        f"<li>{escape(p.upper())}: {n} extreme cases</li>"
        for p, n in by_principle.items()
    )
    return f"""
<div class="header">
  <h1>Calibration Session Worksheet</h1>
  <p class="session-info">
    This worksheet contains <strong>{n_cases}</strong> methods where the two raters
    gave opposite-extreme scores (one rated <em>Violated</em>, the other
    <em>Compliant</em>). These are the most informative cases for aligning
    rubric application.
  </p>
  <ul class="session-info">{rows}</ul>
  <p class="session-info"><strong>Process for each case:</strong></p>
  <ol class="session-info">
    <li>Read the method silently (1 minute).</li>
    <li>Each rater explains their score and reasoning.</li>
    <li>Compare to the rubric criterion shown.</li>
    <li>Agree on a final score (0, 1, or 2). If still uncertain, mark "1".</li>
    <li>Write a one-line rationale. This will become a calibration note.</li>
  </ol>
  <p class="session-info"><strong>Time budget:</strong> ~2 minutes per case = 70 minutes for {n_cases} cases. Take a 10-minute break halfway through.</p>
</div>
"""


def render_case(idx: int, total: int, row: pd.Series, sample_lookup: dict) -> str:
    method_id = row["method_id"]
    principle = row["principle"]
    rater_scores = json.loads(row["rater_scores"])

    method = sample_lookup.get(method_id)
    if method is None:
        return (
            f'<div class="case"><h3>Case {idx + 1} / {total}</h3>'
            f'<p>Method <code>{escape(method_id)}</code> not found in sample.</p></div>'
        )

    # Extract scores
    score_a = score_b = "?"
    for k, v in rater_scores.items():
        if v is None:
            continue
        if "annotator_a" in k:
            score_a = int(v)
        elif "annotator_b" in k:
            score_b = int(v)

    rubric = RUBRIC_SUMMARY.get(principle, {})
    project = method.get("project", "")
    file_path = method.get("file_path", "")
    startline = method.get("startline", "")
    endline = method.get("endline", "")
    method_name = method.get("method_name", "")
    method_loc = method.get("method_loc", "")
    source = method.get("method_source", "") or ""

    extra_dip = ""
    if principle == "dip":
        extra_dip = f'<p style="font-size:12px; margin-top:6px;">{NOT_DIP_VIOLATIONS}</p>'

    return f"""
<div class="case">
  <h3>Case {idx + 1} of {total}: {escape(principle.upper())}</h3>
  <div class="case-meta">
    <strong>{escape(method_name)}</strong> &middot;
    project <code>{escape(project)}</code> &middot;
    LOC <code>{escape(str(method_loc))}</code><br>
    <code>{escape(file_path)}:{escape(str(startline))}-{escape(str(endline))}</code>
  </div>
  <pre class="code">{escape(source)}</pre>

  <div class="scores">
    <div><strong>Annotator A:</strong> {score_a} &mdash; {label_for(score_a)}</div>
    <div><strong>Annotator B:</strong> {score_b} &mdash; {label_for(score_b)}</div>
  </div>

  <div class="rubric-box">
    <strong>Rubric for {escape(principle.upper())} ({rubric_principle_long(principle)}):</strong>
    <ul>
      <li><strong>0 (Violated):</strong> {rubric.get("0", "")}</li>
      <li><strong>1 (Partial / Uncertain):</strong> {rubric.get("1", "")}</li>
      <li><strong>2 (Compliant):</strong> {rubric.get("2", "")}</li>
    </ul>
    {extra_dip}
  </div>

  <div class="decision">
    <strong>Agreed decision:</strong>
    <div class="checkbox-row">
      <label><input type="radio" name="case_{idx}_score"> 0 &mdash; Violated</label>
      <label><input type="radio" name="case_{idx}_score"> 1 &mdash; Partial</label>
      <label><input type="radio" name="case_{idx}_score"> 2 &mdash; Compliant</label>
    </div>
    <label>Rationale (one sentence, will become calibration note):</label>
    <textarea rows="2" placeholder="e.g., 'static call to Files.copy is JDK utility, not replaceable collaborator → score 2'"></textarea>
    <label>Pattern flag (check if this case represents a recurring boundary issue):</label>
    <div class="checkbox-row">
      <label><input type="checkbox"> Recurring pattern (note in addendum)</label>
    </div>
  </div>
</div>
"""


def label_for(score):
    if score == 0:
        return "Violated"
    if score == 1:
        return "Partial"
    if score == 2:
        return "Compliant"
    return "?"


def rubric_principle_long(p: str) -> str:
    return {
        "srp": "Single Responsibility — method cohesion",
        "ocp": "Open/Closed — modification-risk signals",
        "dip": "Dependency Inversion — replaceable-dependency signals",
    }.get(p, p)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extreme", required=True, type=Path,
                        help="extreme_cases_for_session.csv (0_vs_2 disagreements)")
    parser.add_argument("--sample", required=True, type=Path,
                        help="holdout_sample.csv (for method source)")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    extreme = pd.read_csv(args.extreme)
    sample = pd.read_csv(args.sample)
    sample["method_id"] = sample["method_id"].astype(str)
    sample_lookup = sample.set_index("method_id").to_dict(orient="index")

    # Sort: SRP first, then OCP, then DIP, so the principle context stays
    # together in the session
    principle_order = {"srp": 0, "ocp": 1, "dip": 2}
    extreme["__order"] = extreme["principle"].map(principle_order)
    extreme = extreme.sort_values(["__order", "method_id"]).drop(columns="__order").reset_index(drop=True)

    by_principle = extreme["principle"].value_counts().to_dict()

    parts = [HTML_HEAD, render_header(len(extreme), by_principle)]
    for idx, row in extreme.iterrows():
        parts.append(render_case(idx, len(extreme), row, sample_lookup))
    parts.append("</body></html>")

    args.output.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote worksheet with {len(extreme)} cases to {args.output}")


if __name__ == "__main__":
    main()