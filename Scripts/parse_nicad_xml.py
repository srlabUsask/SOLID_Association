import os
import sys
import argparse
import csv
from xml.etree import ElementTree as ET
from collections import defaultdict


# ── Type priority ─────────────────────────────────────────────────────────────

TYPE_PRIORITY = {"T1": 1, "T2": 2, "T3": 3}

# ── Path normalisation ────────────────────────────────────────────────────────

def normalise_path(file_path):
    if not file_path:
        return ""
    if "/src/" in file_path:
        return file_path.split("/src/")[-1]
    return os.path.basename(file_path)


# ── File type detection ───────────────────────────────────────────────────────

def detect_clone_type(filename):
    f = filename.lower()

    if "classes" not in f or not f.endswith(".xml"):
        return None

    is_blind = "blind" in f
    is_30    = "0_30" in f or "0.30" in f
    is_00    = "0_00" in f or "0.00" in f

    if is_blind and is_30:
        return "T3"
    if is_blind and is_00:
        return "T2"
    if not is_blind and is_00:
        return "T1"

    return None


def infer_project_from_filename(filename):
    PROJECT_MAP = {
        "commons-lang-master":   "commonslang",
        "fitnesse-master":       "fitnesse",
        "hibernate-orm-main":    "hibernate-orm",
        "jackson-databind-2.19": "jackson-databind_",
        "jmeter-master":         "jmeter",
        "junit5-main":           "junit5",
        "selenium-trunk":        "selenium-trunk",
        "struts-main":           "struts",
    }
    base = os.path.basename(filename)
    raw = base.split("_")[0] if "_" in base else base.replace(".xml", "")
    return PROJECT_MAP.get(raw, raw)


# ── Discover files in batch directory ────────────────────────────────────────

def discover_project_files(batch_dir):
    projects = defaultdict(dict)

    for root_dir, dirs, files in os.walk(batch_dir):
        depth = root_dir.replace(batch_dir, "").count(os.sep)
        if depth > 1:
            continue

        for fname in sorted(files):
            clone_type = detect_clone_type(fname)
            if clone_type is None:
                continue

            subfolder = os.path.basename(root_dir)
            if subfolder != os.path.basename(batch_dir):
                project = subfolder
            else:
                project = infer_project_from_filename(fname)

            fpath = os.path.join(root_dir, fname)

            if clone_type in projects[project]:
                print(f"  [WARN] Duplicate {clone_type} for {project}, "
                      f"keeping: {projects[project][clone_type]}")
            else:
                projects[project][clone_type] = fpath

    return dict(projects)


# ── Core parser ───────────────────────────────────────────────────────────────

def parse_classes_xml(xml_path, clone_type_label):
    """Parse a NiCad *-classes.xml and return list of fragment dicts."""
    if not os.path.exists(xml_path):
        print(f"  [ERROR] File not found: {xml_path}")
        return []

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        print(f"  [ERROR] XML parse error in {xml_path}: {e}")
        return []

    root = tree.getroot()

    # Print config validation line
    sysinfo = root.find("systeminfo")
    if sysinfo is not None:
        print(f"         config: granularity={sysinfo.get('granularity','?')}  "
              f"threshold={sysinfo.get('threshold','?')}  "
              f"minlines={sysinfo.get('minlines','?')}")

    fragments = []
    n_classes = 0

    for clone_class in root.findall("class"):
        class_id     = clone_class.get("classid", "")
        class_size   = int(clone_class.get("nclones", 0))
        class_nlines = int(clone_class.get("nlines", 0))

        for source in clone_class.findall("source"):
            file_path = source.get("file", "").strip()
            startline = source.get("startline", "")
            endline   = source.get("endline", "")

            if not file_path or not startline:
                continue
            try:
                startline = int(startline)
                endline   = int(endline) if endline else startline
            except ValueError:
                continue

            fragments.append({
                "file_path":    file_path,
                "startline":    startline,
                "endline":      endline,
                "clone_type":   clone_type_label,
                "class_id":     class_id,
                "class_nlines": class_nlines,
                "class_size":   class_size,
            })

        n_classes += 1

    print(f"         {n_classes} clone classes  |  {len(fragments)} fragments")
    return fragments


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_fragments(all_fragments):
    """Collapse to one row per unique (file_path, startline)."""
    method_map = defaultdict(lambda: {
        "endline":      0,
        "clone_type":   "T1",
        "class_ids":    set(),
        "clone_nlines": 0,
    })

    for frag in all_fragments:
        key = (frag["file_path"], frag["startline"])
        rec = method_map[key]

        rec["endline"] = max(rec["endline"], frag["endline"])

        if TYPE_PRIORITY.get(frag["clone_type"], 0) > \
           TYPE_PRIORITY.get(rec["clone_type"], 0):
            rec["clone_type"] = frag["clone_type"]

        cid = f"{frag['clone_type']}:{frag['class_id']}"
        rec["class_ids"].add(cid)
        rec["clone_nlines"] = max(rec["clone_nlines"], frag["class_nlines"])

    rows = []
    for (file_path, startline), rec in sorted(method_map.items()):
        rows.append({
            "file_path":    normalise_path(file_path),
            "file_path_raw": file_path,
            "startline":    startline,
            "endline":      rec["endline"],
            "is_cloned":    1,
            "clone_type":   rec["clone_type"],
            "nclasses":     len(rec["class_ids"]),
            "class_ids":    ";".join(sorted(rec["class_ids"])),
            "clone_nlines": rec["clone_nlines"],
        })

    return rows


# ── Per-project processing ────────────────────────────────────────────────────

def process_project(project, type_paths, output_dir):
    """Parse all available clone type files for one project."""
    print(f"\n{'='*60}")
    print(f"  Project : {project}")
    print(f"{'='*60}")

    found_types   = [t for t in ["T1","T2","T3"] if t in type_paths]
    missing_types = [t for t in ["T1","T2","T3"] if t not in type_paths]

    for t in found_types:
        print(f"  [{t}] {os.path.basename(type_paths[t])}")
    if missing_types:
        print(f"  [WARN] Missing: {missing_types} — results will be incomplete")

    all_fragments = []
    for t in found_types:
        frags = parse_classes_xml(type_paths[t], t)
        all_fragments.extend(frags)

    if not all_fragments:
        print(f"  [ERROR] No fragments found for {project}, skipping.")
        return [], {}

    rows = aggregate_fragments(all_fragments)
    for r in rows:
        r["project"] = project

    by_type = defaultdict(int)
    for r in rows:
        by_type[r["clone_type"]] += 1

    total = len(rows)
    multi = sum(1 for r in rows if r["nclasses"] > 1)

    print(f"\n  Unique cloned fragments : {total:,}")
    for t in ["T1", "T2", "T3"]:
        if by_type[t]:
            print(f"    {t}: {by_type[t]:,}  ({by_type[t]/total*100:.1f}%)")
    print(f"  In >1 clone class       : {multi:,}")

    out_path = os.path.join(output_dir, f"{project}_clone_methods.csv")
    write_csv(rows, out_path)

    summary = {
        "project":       project,
        "types_found":   ";".join(found_types),
        "types_missing": ";".join(missing_types),
        "total_cloned":  total,
        "n_T1":          by_type.get("T1", 0),
        "n_T2":          by_type.get("T2", 0),
        "n_T3":          by_type.get("T3", 0),
        "n_multiclass":  multi,
    }

    return rows, summary


# ── Writers ───────────────────────────────────────────────────────────────────

OUTPUT_FIELDS = [
    "project", "file_path", "startline", "endline",
    "is_cloned", "clone_type", "nclasses", "class_ids", "clone_nlines",
    "file_path_raw",
]

SUMMARY_FIELDS = [
    "project", "types_found", "types_missing",
    "total_cloned", "n_T1", "n_T2", "n_T3", "n_multiclass",
]


def write_csv(rows, path, fields=None):
    if fields is None:
        fields = OUTPUT_FIELDS
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved : {path}  ({len(rows):,} rows)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Parse NiCad clone XML files into clone_methods CSVs"
    )

    parser.add_argument("--batch_dir",  default=None,
                        help="Folder with NiCad *-classes.xml files "
                             "(batch mode — processes all projects found)")
    parser.add_argument("--t1",         default=None)
    parser.add_argument("--t2",         default=None)
    parser.add_argument("--t3",         default=None)
    parser.add_argument("--project",    default=None)
    parser.add_argument("--output",     default=None,
                        help="Output CSV path (single project mode)")
    parser.add_argument("--output_dir", default="./results",
                        help="Output directory (batch mode, default: ./results)")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # ── BATCH MODE ────────────────────────────────────────────────────────────
    if args.batch_dir:
        print(f"\nBatch mode: scanning {args.batch_dir}\n")
        project_files = discover_project_files(args.batch_dir)

        if not project_files:
            print("No recognisable NiCad *-classes.xml files found.")
            print("Expected filenames containing:")
            print("  clones-0_00-classes       (T1)")
            print("  blind-clones-0_00-classes (T2)")
            print("  blind-clones-0_30-classes (T3)")
            sys.exit(1)

        print(f"Found {len(project_files)} project(s):")
        for proj, types in sorted(project_files.items()):
            print(f"  {proj:<25} types: {sorted(types.keys())}")

        all_rows      = []
        all_summaries = []

        for project in sorted(project_files.keys()):
            rows, summary = process_project(
                project, project_files[project], args.output_dir
            )
            all_rows.extend(rows)
            if summary:
                all_summaries.append(summary)

        if all_rows:
            write_csv(all_rows,
                      os.path.join(args.output_dir,
                                   "ALL_PROJECTS_clone_methods.csv"))

        if all_summaries:
            write_csv(all_summaries,
                      os.path.join(args.output_dir, "batch_summary.csv"),
                      fields=SUMMARY_FIELDS)

            print(f"\n{'='*65}")
            print("BATCH COMPLETE")
            print(f"{'='*65}")
            print(f"  {'Project':<25} {'T1':>7} {'T2':>7} {'T3':>7} "
                  f"{'Total':>8}  Missing")
            print(f"  {'-'*60}")
            for s in all_summaries:
                print(f"  {s['project']:<25} "
                      f"{s['n_T1']:>7,} "
                      f"{s['n_T2']:>7,} "
                      f"{s['n_T3']:>7,} "
                      f"{s['total_cloned']:>8,}  "
                      f"{s['types_missing'] or '-'}")
            print(f"  {'-'*60}")
            print(f"  {'TOTAL':<25} "
                  f"{sum(s['n_T1'] for s in all_summaries):>7,} "
                  f"{sum(s['n_T2'] for s in all_summaries):>7,} "
                  f"{sum(s['n_T3'] for s in all_summaries):>7,} "
                  f"{sum(s['total_cloned'] for s in all_summaries):>8,}")
            print()

    # ── SINGLE PROJECT MODE ───────────────────────────────────────────────────
    elif any([args.t1, args.t2, args.t3]):
        if not args.output:
            print("ERROR: --output is required in single project mode")
            sys.exit(1)

        project = args.project or infer_project_from_filename(
            args.t1 or args.t2 or args.t3
        )

        type_paths = {}
        if args.t1: type_paths["T1"] = args.t1
        if args.t2: type_paths["T2"] = args.t2
        if args.t3: type_paths["T3"] = args.t3

        out_dir = os.path.dirname(os.path.abspath(args.output))
        rows, _ = process_project(project, type_paths, out_dir)

        if rows:
            write_csv(rows, args.output)

    else:
        print("ERROR: provide --batch_dir or at least one of --t1/--t2/--t3")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()