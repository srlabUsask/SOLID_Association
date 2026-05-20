import re
import pandas as pd

PROJECT_MAP = {
    "commonslang"       : "commonslang_SOLID_Eval",
    "fitnesse"          : "fitnesse_SOLID_Eval",
    "hibernate-orm"     : "hibernate-orm_SOLID_Eval",
    "jackson-databind_" : "jackson-databind__SOLID_Eval",
    "jmeter"            : "jmeter_SOLID_Eval",
    "junit5"            : "junit5_SOLID_Eval",
    "selenium-trunk"    : "selenium-trunk_SOLID_Eval",
    "struts"            : "struts_SOLID_Eval",
}

def normalise_path(p):
    s = str(p).strip()
    if "/src/" in s:
        return s.split("/src/")[-1]
    return None

scores = pd.read_csv("Results/per_method_scores.csv")
clones = pd.read_csv("Results/ALL_PROJECTS_clone_methods.csv")
print(f"scores: {len(scores):,}  clones: {len(clones):,}")

# Prepare method side
scores["norm_path"] = scores["file_path"].apply(normalise_path)
scores["startline"] = scores["startline"].astype(int)
scores["method_loc"] = scores["endline"] - scores["startline"] + 1

# Prepare clone side
raw_col = "file_path_raw" if "file_path_raw" in clones.columns else "file_path"
clones = clones[clones[raw_col].astype(str).str.contains("/src/", na=False)].copy()
clones["norm_path"] = clones[raw_col].astype(str).apply(normalise_path)
clones["startline"] = clones["startline"].astype(int)
clones["project_mapped"] = clones["project"].map(PROJECT_MAP)

# Left-join: methods → clones; methods not in clones get is_cloned=0
merged = scores.merge(
    clones[["project_mapped","norm_path","startline","is_cloned","clone_type"]],
    left_on=["project","norm_path","startline"],
    right_on=["project_mapped","norm_path","startline"],
    how="left",
    indicator=True,
)
merged["is_cloned"]  = merged["is_cloned"].fillna(0).astype(int)
merged["clone_type"] = merged["clone_type"].fillna("none")

# Only keep methods within /src/ analysis tree (NiCad-scope)
linked = merged[merged["norm_path"].notna()].copy()

# Inferential corpus = linked methods (those NiCad could have seen)
print(f"\nLinked corpus: {len(linked):,}  cloned: {linked['is_cloned'].sum():,}  rate: {linked['is_cloned'].mean()*100:.1f}%")

linked.to_csv("Results/inferential_corpus.csv", index=False)
print(f"Wrote Results/inferential_corpus.csv")