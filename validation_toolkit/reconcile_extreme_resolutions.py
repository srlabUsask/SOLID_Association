"""
reconcile_extreme_resolutions.py

Reconciles row-numbered calibration decisions against worksheet ordering
to produce an extreme_resolutions.csv with full method IDs.
"""

import argparse
import csv
import re
import sys
from pathlib import Path


CASE_RE = re.compile(
    r'Case\s+(\d+)\s+of\s+\d+:\s+(\w+).*?<code>([^<]+:\d+-\d+)</code>',
    re.DOTALL,
)


def parse_worksheet(path: Path) -> dict:
    html = path.read_text(encoding="utf-8")
    cases = {}
    for m in CASE_RE.finditer(html):
        case_num = int(m.group(1))
        principle = m.group(2).lower()
        method_id = re.sub(r"\s+", "", m.group(3))
        cases[case_num] = {"principle": principle, "method_id": method_id}
    return cases


def parse_students_csv(path: Path) -> list:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                case_num = int(str(r["method_id"]).strip())
            except (ValueError, TypeError):
                rows.append({
                    "case_num": None,
                    "principle": (r.get("principle") or "").lower().strip(),
                    "agreed_score_raw": (r.get("agreed_score") or "").strip(),
                    "pattern": (r.get("Pattern?") or "").strip(),
                    "rationale": (r.get("Rationale") or "").strip(),
                    "raw_method_id": str(r.get("method_id") or "").strip(),
                })
                continue
            rows.append({
                "case_num": case_num,
                "principle": (r.get("principle") or "").lower().strip(),
                "agreed_score_raw": (r.get("agreed_score") or "").strip(),
                "pattern": (r.get("Pattern?") or "").strip(),
                "rationale": (r.get("Rationale") or "").strip(),
                "raw_method_id": str(case_num),
            })
    return rows


def reconcile(students: list, worksheet: dict) -> tuple:
    resolved = []
    issues = []

    for r in students:
        case_num = r["case_num"]
        if case_num is None:
            issues.append(
                f"Row with method_id='{r['raw_method_id']}' is not a valid "
                f"case number; skipping."
            )
            continue

        if case_num not in worksheet:
            issues.append(f"Case {case_num}: not present in worksheet; skipping.")
            continue

        ws = worksheet[case_num]

        if r["principle"] != ws["principle"]:
            issues.append(
                f"Case {case_num}: principle mismatch (csv={r['principle']}, "
                f"worksheet={ws['principle']}). Using worksheet's principle."
            )

        score_raw = r["agreed_score_raw"].lower()
        if score_raw == "deferred":
            agreed_score = "deferred"
        else:
            try:
                agreed_score = int(score_raw)
                if agreed_score not in (0, 1, 2):
                    raise ValueError
            except ValueError:
                issues.append(
                    f"Case {case_num}: agreed_score='{r['agreed_score_raw']}' "
                    f"is not 0/1/2/deferred; skipping."
                )
                continue

        if (
            ws["principle"] == "dip"
            and agreed_score == 0
            and "no replaceable" in r["rationale"].lower()
        ):
            issues.append(
                f"Case {case_num}: score-rationale mismatch (score=0, "
                f"rationale=\"{r['rationale']}\")."
            )

        resolved.append({
            "method_id": ws["method_id"],
            "principle": ws["principle"],
            "agreed_score": agreed_score,
            "pattern": r["pattern"],
            "rationale": r["rationale"],
        })

    covered = {r["case_num"] for r in students if r["case_num"] is not None}
    for case_num in sorted(worksheet.keys()):
        if case_num not in covered:
            issues.append(
                f"Case {case_num} ({worksheet[case_num]['principle']}, "
                f"{worksheet[case_num]['method_id']}): no decision in "
                f"student CSV."
            )

    return resolved, issues


def write_resolved(resolved: list, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "method_id", "principle", "agreed_score", "pattern", "rationale"
        ])
        writer.writeheader()
        for row in resolved:
            writer.writerow(row)


def write_report(issues: list, resolved: list, path: Path,
                 worksheet: dict) -> None:
    from collections import Counter
    lines = []
    lines.append("Reconciliation report")
    lines.append("=" * 60)
    lines.append(f"Worksheet cases: {len(worksheet)}")
    lines.append(f"Resolved decisions: {len(resolved)}")
    lines.append(f"Deferred to PI: "
                 f"{sum(1 for r in resolved if r['agreed_score'] == 'deferred')}")
    lines.append(f"Issues flagged: {len(issues)}")
    lines.append("")
    lines.append("Score distribution per principle:")
    for p in ("srp", "ocp", "dip"):
        scores = [r["agreed_score"] for r in resolved if r["principle"] == p]
        n = len(scores)
        c = Counter(scores)
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(c.items(), key=str))
        lines.append(f"  {p.upper()} (n={n}): {breakdown}")
    lines.append("")
    if issues:
        lines.append("Issues:")
        for i, issue in enumerate(issues, 1):
            lines.append(f"  [{i}] {issue}")
    else:
        lines.append("No issues flagged.")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--students", required=True, type=Path)
    parser.add_argument("--worksheet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    worksheet = parse_worksheet(args.worksheet)
    if not worksheet:
        sys.exit("ERROR: no cases parsed from worksheet HTML.")

    students = parse_students_csv(args.students)
    resolved, issues = reconcile(students, worksheet)

    write_resolved(resolved, args.output)
    write_report(issues, resolved, args.report, worksheet)

    print(f"Worksheet cases: {len(worksheet)}", file=sys.stderr)
    print(f"Student decisions: {len(students)}", file=sys.stderr)
    print(f"Resolved (written to {args.output}): {len(resolved)}", file=sys.stderr)
    print(f"Issues flagged (see {args.report}): {len(issues)}", file=sys.stderr)
    if issues:
        print("\nFirst few issues:", file=sys.stderr)
        for issue in issues[:5]:
            print(f"  - {issue}", file=sys.stderr)


if __name__ == "__main__":
    main()
