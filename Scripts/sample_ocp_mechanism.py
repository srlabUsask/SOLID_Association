import argparse
import re
import pandas as pd

PROJECT_MAP = {
    "commonslang_SOLID_Eval":       "commonslang",
    "fitnesse_SOLID_Eval":          "fitnesse",
    "hibernate-orm_SOLID_Eval":     "hibernate-orm",
    "jackson-databind__SOLID_Eval": "jackson-databind_",
    "jmeter_SOLID_Eval":            "jmeter",
    "junit5_SOLID_Eval":            "junit5",
    "selenium-trunk_SOLID_Eval":    "selenium-trunk",
    "struts_SOLID_Eval":            "struts",
}

def normalize_path(p: str) -> str:
    """Reduce to post-/src/ segment, matching the methodology's join key."""
    if not isinstance(p, str):
        return p
    m = re.search(r"/src/(.+)$", p)
    return m.group(1) if m else p

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores",  required=True)
    parser.add_argument("--clones",  required=True)
    parser.add_argument("--corpus",  required=True)
    parser.add_argument("--output",  default="Results/ocp_mechanism_sample.csv")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    scores = pd.read_csv(args.scores)
    clones = pd.read_csv(args.clones)
    corpus = pd.read_csv(args.corpus,
                         usecols=["project","file_path","startline","method_loc","method_source"])
    print(f"scores: {len(scores):,}  clones: {len(clones):,}  corpus: {len(corpus):,}")

    # Normalize projects
    scores["project"] = scores["project"].map(lambda p: PROJECT_MAP.get(p, p))
    corpus["project"] = corpus["project"].map(lambda p: PROJECT_MAP.get(p, p))

    # Normalize paths to post-/src/ segment
    scores["file_path"] = scores["file_path"].map(normalize_path)
    corpus["file_path"] = corpus["file_path"].map(normalize_path)
    # clones already post-/src/ (e.g., "main/java/...")

    # Sanity peek
    print("Sample SCORES path:", scores["file_path"].iloc[0])
    print("Sample CLONES path:", clones["file_path"].iloc[0])

    # Join
    df = scores.merge(
        clones[["project","file_path","startline","is_cloned","clone_type"]],
        on=["project","file_path","startline"], how="inner",
    )
    print(f"After scores⨝clones: {len(df):,}")

    df = df.merge(corpus, on=["project","file_path","startline"], how="left")
    df = df.dropna(subset=["method_loc","method_source"])
    print(f"After corpus enrichment: {len(df):,}")

    eligible = df[(df["method_loc"] >= 10) & (df["ocp"] == 2) & (df["is_cloned"] == 1)].copy()
    print(f"Q4 + OCP=2 + cloned: {len(eligible):,}")
    print(eligible["project"].value_counts().to_string())

    sample = eligible.sample(n=min(args.n, len(eligible)), random_state=args.seed)
    print(f"\nSampled {len(sample)}:")
    print(sample["project"].value_counts().to_string())

    cols = ["method_id","project","file_path","startline","endline",
            "method_loc","srp","ocp","dip","clone_type","method_source"]
    sample[cols].to_csv(args.output, index=False)
    print(f"\nWrote {args.output}")

if __name__ == "__main__":
    main()