"""Check the authoritative dataset and regenerated C/E/F against preserved results."""
import ast
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_paths import require_analysis, RESULTS_DIR


def main():
    checks = []

    def check(name, condition, detail=""):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    manifest = json.loads((ROOT / "preservation/manifest.json").read_text())
    with zipfile.ZipFile(ROOT / "preservation/original_notebooks_and_results.zip") as archive:
        check("original archive checksum verification", all(
            hashlib.sha256(archive.read(x["path"])).hexdigest() == x["sha256"]
            for x in manifest if x["archived"]))

    path = require_analysis()
    sha = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    expected_sha = next(x["sha256"] for x in manifest if x["path"].endswith("analysis_ready.parquet"))
    check("authoritative Parquet unchanged", sha == expected_sha, sha)
    df = pd.read_parquet(path)
    check("dataset dimensions", df.shape == (1_093_847, 52), str(df.shape))
    check("unique review IDs", df.review_id.is_unique)
    check("product and author keys present", df[["product_id", "author_id"]].notna().all().all())
    check("product count", df.product_id.nunique() == 2351)
    check("ratings and five_star agree", df.rating.isin([1, 2, 3, 4, 5]).all()
          and (df.five_star == df.rating.eq(5).astype(int)).all())
    check("rating distribution", df.rating.value_counts().sort_index().tolist() ==
          [61197, 53011, 81791, 199317, 698531])
    check("secondary outcome missingness", df.recommended.isna().sum() == 167816
          and df.recommended.dropna().isin([0, 1]).all())
    check("secondary outcome absent before 2017", df.loc[df.review_year < 2017, "recommended"].isna().all())
    levels = {
        "price_segment": ["Budget (<$25)", "Mid ($25-49)", "Premium ($50-99)", "Luxury ($100+)"],
        "skin_type_cat": ["Normal", "Combination", "Dry", "Oily", "Not reported"],
        "category": ["Moisturizers", "Treatments", "Cleansers", "Eye Care", "Masks", "Lip Care",
                     "Sunscreen", "Minis & Sets", "Tools, Wellness & Self-Tan"],
    }
    highlights = [c for c in df if c.startswith("hl_")] + ["highlights_missing"]
    predictors = list(levels) + highlights
    check("model columns complete", not df[predictors + ["five_star"]].isna().any().any())
    check("fixed categories and references", all(list(df[c].cat.categories) == values
                                               for c, values in levels.items()))
    check("binary highlight indicators", df[highlights].isin([0, 1]).all().all())
    check("no highlights implies no claims", df.loc[df.highlights_missing.eq(1), highlights[:-1]].eq(0).all().all())
    product_vars = ["price_usd", "log_price", "price_segment", "category", "n_highlights"] + highlights
    check("product covariates constant within product", not df.groupby("product_id")[product_vars]
          .nunique(dropna=False).gt(1).any().any())
    check("positive finite prices and log transform", (df.price_usd > 0).all()
          and np.isfinite(df.price_usd).all() and np.allclose(df.log_price, np.log(df.price_usd)))
    check("fixed price bins", (df.price_segment == pd.cut(df.price_usd, [0,25,50,100,np.inf],
                                                        labels=levels["price_segment"], right=False)).all())
    for col, prefix in [("price_segment", "x_price_"), ("category", "x_cat_"), ("skin_type_cat", "x_skin_")]:
        columns = [c for c in df if c.startswith(prefix)]
        sums = df[columns].sum(axis=1)
        expected = pd.get_dummies(df[col], drop_first=True).to_numpy(dtype=int)
        check(f"{col} one-hot encoding", np.array_equal(df[columns].to_numpy(), expected)
              and ((sums == 0) == (df[col] == levels[col][0])).all())
    pair_sizes = df.groupby(["author_id", "product_id"])["review_id"].transform("size")
    check("repeat-review counts and flags", (df.n_reviews_same_author_product == pair_sizes).all()
          and (df.repeat_author_product == (pair_sizes > 1).astype(int)).all())
    check("date features", (df.review_date.dt.year == df.review_year).all()
          and (df.recent_review == (df.review_year >= 2020).astype(int)).all())
    cell_counts = df.groupby(["price_segment", "skin_type_cat"], observed=True).agg(
        reviews=("review_id", "size"), products=("product_id", "nunique"))
    check("interaction cell coverage", len(cell_counts) == 20 and cell_counts.reviews.min() >= 1000
          and cell_counts.products.min() >= 100)
    split_summary = []
    for label, data in [("full", df), ("recommendation", df[df.recommended.notna()])]:
        tr, te = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=5106)
                      .split(data, groups=data.product_id))
        train_products, test_products = set(data.iloc[tr].product_id), set(data.iloc[te].product_id)
        check(f"{label} product-disjoint evaluation", train_products.isdisjoint(test_products))
        split_summary.append({"sample": label, "n_reviews": len(data), "train_reviews": len(tr),
                              "test_reviews": len(te), "train_products": len(train_products),
                              "test_products": len(test_products)})
    for p in [*ROOT.glob("Part */*.ipynb"), *ROOT.glob("Part */Python Scripts/*.py")]:
        if p.suffix == ".ipynb":
            for i, cell in enumerate(json.loads(p.read_text())["cells"]):
                if cell["cell_type"] == "code":
                    ast.parse("".join(cell["source"]), filename=f"{p.name}: cell {i}")
        else:
            ast.parse(p.read_text(), filename=p.name)
    check("all A/B/C/E notebook cells and F scripts parse", True)
    execution = json.loads((RESULTS_DIR / "execution.json").read_text())
    check("C/E/F executed successfully", all(s["exit_code"] == 0 for s in execution["steps"])
          and {s["part"] for s in execution["steps"]} >= set("CEF")
          and execution["analysis_sha256"] == sha)

    # Compare every supplied C/E/F CSV, using the immutable pre-edit archive.
    comparisons = []
    with zipfile.ZipFile(ROOT / "preservation/original_notebooks_and_results.zip") as archive:
        for name in archive.namelist():
            if not name.endswith(".csv") or not name.startswith(("Part C.", "Part E.", "Part F.")):
                continue
            part = name[5].lower()
            target = RESULTS_DIR / f"part_{part}" / Path(name).name
            row = {"part": part.upper(), "file": Path(name).name, "passed": False}
            if not target.is_file():
                row["detail"] = "regenerated file missing"
                comparisons.append(row)
                continue
            original = pd.read_csv(io.BytesIO(archive.read(name)))
            current = pd.read_csv(target)
            try:
                # Narrative reference labels are clarified in the two log-price summaries.
                for frame in (original, current):
                    if Path(name).name in ["log_price_odds_ratios.csv", "table3_log_price_sensitivity.csv"]:
                        frame.drop(columns=[c for c in ["scale", "Scale"] if c in frame], inplace=True)
                    if "term" in frame:
                        frame["term"] = frame["term"].str.replace(" × ", " x ", regex=False)
                assert set(original.columns) == set(current.columns), "columns differ"
                current = current[original.columns]
                # Category order can differ, so align by all nonnumeric keys.
                keys = [c for c in original if not pd.api.types.is_numeric_dtype(original[c])]
                if keys:
                    original = original.sort_values(keys).reset_index(drop=True)
                    current = current.sort_values(keys).reset_index(drop=True)
                for column in original.select_dtypes(include=["integer", "bool"]):
                    np.testing.assert_array_equal(original[column], current[column])
                tolerance = 1e-6
                pd.testing.assert_frame_equal(original, current, check_dtype=False, check_exact=False,
                                              atol=tolerance, rtol=1e-6)
                numeric = original.select_dtypes(include="number").columns
                delta = np.nanmax(np.abs(original[numeric].to_numpy() - current[numeric].to_numpy())) if len(numeric) else 0.
                row.update(passed=True, max_abs_numeric_difference=float(delta), atol=tolerance)
            except (AssertionError, ValueError) as error:
                row["detail"] = str(error)[:1800]
            comparisons.append(row)

    RESULTS_DIR.mkdir(exist_ok=True)
    pd.DataFrame(comparisons).to_csv(RESULTS_DIR / "result_comparison.csv", index=False)
    check("all supplied C/E/F CSV results reproduced", all(x["passed"] for x in comparisons),
          f"{sum(x['passed'] for x in comparisons)}/{len(comparisons)} files")
    report = {"input": {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                         "sha256": sha, "bytes": path.stat().st_size, "rows": len(df),
                         "columns": df.shape[1], "products": df.product_id.nunique(),
                         "five_star_rate": float(df.five_star.mean()),
                         "recommendation_rows": int(df.recommended.notna().sum())},
              "splits": split_summary, "checks": checks, "comparisons": comparisons,
              "passed": all(x["passed"] for x in checks)}
    (RESULTS_DIR / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    for c in checks:
        print(f"{'PASS' if c['passed'] else 'FAIL'} {c['check']} {c['detail']}")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
