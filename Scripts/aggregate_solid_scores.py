import os
import json
import argparse
import csv
from collections import defaultdict


# ── My Parser ────────────────────────────────────────────────────────────────────

def parse_record(obj, project_name):
    """
    Parse one method JSON object into a flat row dict.
    Returns None if required score fields are missing or malformed.
    """
    try:
        srp = int(obj["srp"]["score"])
        ocp = int(obj["ocp"]["score"])
        dip = int(obj["dip"]["score"])
    except (KeyError, TypeError, ValueError):
        return None

    solid      = srp + ocp + dip          # recomputing; I do not trust stored solid_score by GPT
    method_id  = obj.get("id", "")
    file_path  = obj.get("file_path", "")
    startline  = obj.get("startline", "")
    endline    = obj.get("endline", "")
    model      = obj.get("model", "")
    flags      = ";".join(obj.get("overall", {}).get("flags", []))

    # Confidence values (useful for sensitivity analysis later)
    srp_conf   = obj.get("srp", {}).get("confidence", "")
    ocp_conf   = obj.get("ocp", {}).get("confidence", "")
    dip_conf   = obj.get("dip", {}).get("confidence", "")

    return {
        "project":       project_name,
        "method_id":     method_id,
        "file_path":     file_path,
        "startline":     startline,
        "endline":       endline,
        "srp":           srp,
        "ocp":           ocp,
        "dip":           dip,
        "solid":         solid,
        "srp_conf":      srp_conf,
        "ocp_conf":      ocp_conf,
        "dip_conf":      dip_conf,
        "flags":         flags,
        "model":         model,
        # Binary violation indicators (score == 0)
        "srp_violated":  1 if srp == 0 else 0,
        "ocp_violated":  1 if ocp == 0 else 0,
        "dip_violated":  1 if dip == 0 else 0,
        # Partial/uncertain indicator (score == 1)
        "srp_partial":   1 if srp == 1 else 0,
        "ocp_partial":   1 if ocp == 1 else 0,
        "dip_partial":   1 if dip == 1 else 0,
    }


# ── Loader ────────────────────────────────────────────────────────────────────

def load_ndjson_dir(data_dir):
    """
    Read all .json files in data_dir.
    Each file is NDJSON: one JSON object per line.
    Project name = filename without extension.
    """
    all_rows = []
    skipped  = 0

    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".json"):
            continue

        project_name = fname.replace(".json", "")
        fpath        = os.path.join(data_dir, fname)
        file_rows    = 0
        file_skipped = 0

        with open(fpath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  [WARN] {fname} line {line_num}: JSON parse error — {e}")
                    file_skipped += 1
                    continue

                row = parse_record(obj, project_name)
                if row:
                    all_rows.append(row)
                    file_rows += 1
                else:
                    file_skipped += 1

        print(f"  {project_name:<30} {file_rows:>6} methods loaded"
              + (f"  ({file_skipped} skipped)" if file_skipped else ""))
        skipped += file_skipped

    print(f"\n  Total: {len(all_rows)} methods loaded, {skipped} skipped\n")
    return all_rows


# ── Aggregation ───────────────────────────────────────────────────────────────

def compute_project_summary(rows):
    """
    Per-project metrics used directly in the paper:
      - total_methods
      - mean_srp / mean_ocp / mean_dip / mean_solid
      - srp_violation_rate / ocp_violation_rate / dip_violation_rate
          → proportion of methods with score = 0 (clear violation)
      - srp_partial_rate / ocp_partial_rate / dip_partial_rate
          → proportion of methods with score = 1 (uncertain / needs_more_context)
      - pct_needs_more_context
          → proportion of methods with any needs_more_context flag
    """
    by_project = defaultdict(list)
    for row in rows:
        by_project[row["project"]].append(row)

    summaries = []
    for project in sorted(by_project):
        methods = by_project[project]
        n = len(methods)

        def mean(key):
            return round(sum(m[key] for m in methods) / n, 4)

        def rate(key):
            return round(sum(m[key] for m in methods) / n, 4)

        pct_nmc = round(
            sum(1 for m in methods if "needs_more_context" in m["flags"]) / n, 4
        )

        summaries.append({
            "project":              project,
            "total_methods":        n,
            "mean_srp":             mean("srp"),
            "mean_ocp":             mean("ocp"),
            "mean_dip":             mean("dip"),
            "mean_solid":           mean("solid"),
            "srp_violation_rate":   rate("srp_violated"),
            "ocp_violation_rate":   rate("ocp_violated"),
            "dip_violation_rate":   rate("dip_violated"),
            "srp_partial_rate":     rate("srp_partial"),
            "ocp_partial_rate":     rate("ocp_partial"),
            "dip_partial_rate":     rate("dip_partial"),
            "pct_needs_more_context": pct_nmc,
        })

    return summaries


def compute_score_distributions(rows):
    """
    For each project × principle, count how many methods scored 0, 1, 2.
    Useful for bar charts / violin plots in the paper.
    """
    by_project = defaultdict(list)
    for row in rows:
        by_project[row["project"]].append(row)

    dist_rows = []
    for project in sorted(by_project):
        methods = by_project[project]
        for principle in ("srp", "ocp", "dip"):
            counts = {0: 0, 1: 0, 2: 0}
            for m in methods:
                counts[m[principle]] += 1
            n = len(methods)
            dist_rows.append({
                "project":   project,
                "principle": principle.upper(),
                "score_0":   counts[0],
                "score_1":   counts[1],
                "score_2":   counts[2],
                "pct_0":     round(counts[0] / n, 4),
                "pct_1":     round(counts[1] / n, 4),
                "pct_2":     round(counts[2] / n, 4),
            })

    return dist_rows


# ── Writers ───────────────────────────────────────────────────────────────────

METHOD_FIELDS = [
    "project", "method_id", "file_path", "startline", "endline",
    "srp", "ocp", "dip", "solid",
    "srp_conf", "ocp_conf", "dip_conf",
    "srp_violated", "ocp_violated", "dip_violated",
    "srp_partial", "ocp_partial", "dip_partial",
    "flags", "model",
]

SUMMARY_FIELDS = [
    "project", "total_methods",
    "mean_srp", "mean_ocp", "mean_dip", "mean_solid",
    "srp_violation_rate", "ocp_violation_rate", "dip_violation_rate",
    "srp_partial_rate", "ocp_partial_rate", "dip_partial_rate",
    "pct_needs_more_context",
]

DIST_FIELDS = [
    "project", "principle",
    "score_0", "score_1", "score_2",
    "pct_0", "pct_1", "pct_2",
]


def write_csv(rows, fields, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved: {path}  ({len(rows)} rows)")


# ── Console summary table ─────────────────────────────────────────────────────

def print_summary_table(summaries):
    print("\n" + "─" * 95)
    print(f"{'Project':<25} {'N':>7}  {'SOLID':>6}  "
          f"{'SRP_viol':>9}  {'OCP_viol':>9}  {'DIP_viol':>9}  {'NMC%':>6}")
    print("─" * 95)
    for s in summaries:
        print(
            f"{s['project']:<25} "
            f"{s['total_methods']:>7}  "
            f"{s['mean_solid']:>6.3f}  "
            f"{s['srp_violation_rate']:>9.3f}  "
            f"{s['ocp_violation_rate']:>9.3f}  "
            f"{s['dip_violation_rate']:>9.3f}  "
            f"{s['pct_needs_more_context']:>6.3f}"
        )
    print("─" * 95)
    total_n = sum(s["total_methods"] for s in summaries)
    print(f"{'TOTAL':<25} {total_n:>7}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Aggregate SOLID scoring NDJSON files into CSVs"
    )
    parser.add_argument(
        "--data_dir", required=True,
        help="Folder containing one NDJSON file per project (e.g. struts.json)"
    )
    parser.add_argument(
        "--output_dir", default="./results",
        help="Where to write output CSVs (default: ./results)"
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"\nLoading NDJSON files from: {args.data_dir}\n")
    rows = load_ndjson_dir(args.data_dir)

    if not rows:
        print("No valid records found. Check --data_dir and JSON structure.")
        return

    # 1. Per-method CSV
    write_csv(rows, METHOD_FIELDS,
              os.path.join(args.output_dir, "per_method_scores.csv"))

    # 2. Project summary CSV
    summaries = compute_project_summary(rows)
    write_csv(summaries, SUMMARY_FIELDS,
              os.path.join(args.output_dir, "project_summary.csv"))

    # 3. Score distributions CSV
    distributions = compute_score_distributions(rows)
    write_csv(distributions, DIST_FIELDS,
              os.path.join(args.output_dir, "score_distributions.csv"))

    # Console table
    print_summary_table(summaries)


if __name__ == "__main__":
    main()