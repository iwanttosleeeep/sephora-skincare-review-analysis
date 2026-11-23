"""Rerun A in fresh directories and independently audit raw-to-merged values."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_paths import require_analysis, require_merged
from scripts.compare_part_b import storage_comparison

REVIEW_FILES = ["reviews_0-250.csv", "reviews_250-500.csv", "reviews_500-750.csv",
                "reviews_750-1250.csv", "reviews_1250-end.csv"]
DEMOGRAPHICS = ["skin_tone", "eye_color", "skin_type", "hair_color"]
REVIEW_STRINGS = ["author_id", "product_id", "review_text", "review_title", *DEMOGRAPHICS,
                  "source_file", "product_name", "brand_name"]
PRODUCT_STRINGS = ["product_id", "product_name", "brand_id", "brand_name", "size", "variation_type",
                   "variation_value", "variation_desc", "ingredients", "highlights", "primary_category",
                   "secondary_category", "tertiary_category"]
EXCLUDED_DUPLICATE_FIELDS = ["helpfulness", "total_feedback_count", "total_neg_feedback_count",
                             "total_pos_feedback_count", "source_file"]


def fingerprint(path):
    with path.open("rb") as stream:
        return {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def relative(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def equal_values(left, right):
    """NA-safe exact value comparison, with metadata reported separately."""
    if isinstance(left.dtype, pd.CategoricalDtype) or isinstance(right.dtype, pd.CategoricalDtype):
        left, right = left.astype(object), right.astype(object)
    return left.eq(right).fillna(False) | (left.isna() & right.isna())


def normalise(frame, table):
    """Independent implementation of the notebook's declared type/missing rules."""
    frame = frame.drop(columns=[c for c in frame if c.startswith("Unnamed:")]).copy()
    for col in REVIEW_STRINGS if table == "reviews" else PRODUCT_STRINGS:
        if col in frame:
            text = frame[col].astype("string").str.strip()
            frame[col] = text.mask(text.str.casefold().isin(["", "nan", "none", "null", "n/a", "na"]))
    integers = (["rating", "total_feedback_count", "total_neg_feedback_count", "total_pos_feedback_count"]
                if table == "reviews" else ["loves_count", "reviews", "child_count"])
    floats = (["helpfulness", "price_usd"] if table == "reviews" else
              ["rating", "price_usd", "value_price_usd", "sale_price_usd", "child_max_price", "child_min_price"])
    for col in integers + floats:
        if col in frame:
            numeric = pd.to_numeric(frame[col], errors="coerce")
            dtype = "Int64" if col in integers and not (numeric.dropna() % 1).ne(0).any() else "Float64"
            frame[col] = numeric.astype(dtype)
    booleans = (["is_recommended"] if table == "reviews" else
                ["limited_edition", "new", "online_only", "out_of_stock", "sephora_exclusive"])
    mapping = {"1": True, "0": False, "1.0": True, "0.0": False, "true": True, "false": False}
    for col in booleans:
        if col in frame:
            frame[col] = frame[col].astype("string").str.strip().str.casefold().map(mapping).astype("boolean")
    if table == "reviews":
        frame["submission_time"] = pd.to_datetime(frame.submission_time, format="%Y-%m-%d", errors="coerce")
    return frame


def independent_audit(raw_dir, rebuilt, report_dir):
    checks, files = [], []

    def check(name, passed, **details):
        checks.append({"check": name, "passed": bool(passed), **details})

    frames = []
    for name in REVIEW_FILES:
        frame = pd.read_csv(raw_dir / name, low_memory=False, dtype={"author_id": "string", "product_id": "string"})
        files.append({"file": name, "rows": len(frame), "columns": len(frame.columns)})
        frame["source_file"] = name
        frames.append(frame)
    reviews = normalise(pd.concat(frames, ignore_index=True), "reviews")
    del frames
    raw_count = len(reviews)
    subset = [c for c in reviews if c not in EXCLUDED_DUPLICATE_FIELDS]
    drop_mask = reviews.duplicated(subset=subset, keep="first")
    removed = int(drop_mask.sum())
    reviews = reviews.loc[~drop_mask].reset_index(drop=True)
    check("raw review count reconciles with duplicate removals", raw_count - removed == len(rebuilt),
          raw_rows=raw_count, removed_duplicates=removed, expected_retained=len(reviews), rebuilt_rows=len(rebuilt))
    check("review columns retained", set(reviews.columns) <= set(rebuilt.columns))
    check("all review values correct before allowed demographic fills", len(reviews) == len(rebuilt) and
          all(equal_values(reviews[c], rebuilt[c]).all() for c in reviews if c not in DEMOGRAPHICS))
    check("review IDs preserved from lexical raw input", len(reviews) == len(rebuilt) and
          all(equal_values(reviews[c], rebuilt[c]).all() for c in ["author_id", "product_id"]))
    check("review product IDs present", rebuilt.product_id.notna().all())
    check("review author IDs present", rebuilt.author_id.notna().all())
    check("review dates valid", rebuilt.submission_time.notna().all())
    fills = []
    if len(reviews) == len(rebuilt):
        for col in DEMOGRAPHICS:
            before, after = reviews[col], rebuilt[col]
            distinct = before.str.casefold().groupby(reviews.author_id).nunique()
            first = before.groupby(reviews.author_id).first()
            eligible = reviews.author_id.map(distinct).eq(1)
            should_fill = before.isna() & eligible
            expected = before.where(~should_fill, reviews.author_id.map(first))
            observed = before.notna()
            conflict_missing = before.isna() & reviews.author_id.map(distinct).gt(1)
            check(f"{col}: expected same-author fills and all values", equal_values(expected, after).all())
            check(f"{col}: observed values never overwritten", equal_values(before[observed], after[observed]).all())
            check(f"{col}: conflicting authors not imputed", after[conflict_missing].isna().all())
            fills.append({"attribute": col, "missing_before": int(before.isna().sum()),
                          "values_filled": int(should_fill.sum()), "missing_after": int(after.isna().sum()),
                          "expected_values_match": bool(equal_values(expected, after).all()),
                          "conflicting_missing_rows": int(conflict_missing.sum())})
        # Apply expected fills only in this verification copy for post-fill duplicate counts.
        for col in DEMOGRAPHICS:
            reviews[col] = rebuilt[col]
    post_fill_duplicates = int(rebuilt[subset].duplicated(keep="first").sum())
    pair_sizes = rebuilt.groupby(["author_id", "product_id"]).size()
    products = normalise(pd.read_csv(raw_dir / "product_info.csv", low_memory=False,
                                    dtype={"product_id": "string"}), "products")
    check("catalogue product keys unique and nonmissing", products.product_id.is_unique and products.product_id.notna().all())
    catalogue = products.set_index("product_id")
    check("all review products exist in catalogue", rebuilt.product_id.isin(catalogue.index).all())
    join_columns = []
    for col in products:
        if col == "product_id":
            continue
        target = "product_" + col if col in reviews else col
        expected = rebuilt.product_id.map(catalogue[col])
        passed = target in rebuilt and equal_values(expected, rebuilt[target]).all()
        check(f"catalogue join: {target}", passed)
        join_columns.append({"column": target, "passed": bool(passed)})
    check("join status accurate", rebuilt.product_match_status.eq("matched").all())
    check("exact merged column set", set(rebuilt) == set(reviews) | {c["column"] for c in join_columns} | {"product_match_status"})
    pd.DataFrame(fills).to_csv(report_dir / "independent_imputation.csv", index=False)
    return {"checks": checks, "file_counts": files, "catalogue_rows": len(products),
            "unique_review_products": int(rebuilt.product_id.nunique()),
            "catalogue_products_without_reviews": int((~products.product_id.isin(rebuilt.product_id.unique())).sum()),
            "unique_authors": int(rebuilt.author_id.nunique()),
            "missing_author_ids": int(rebuilt.author_id.isna().sum()),
            "repeated_author_product_pairs": int(pair_sizes.gt(1).sum()),
            "raw_review_rows": raw_count, "duplicate_rows_removed": removed,
            "post_imputation_duplicates": post_fill_duplicates, "imputation": fills,
            "leading_zero_author_rows": int(rebuilt.author_id.str.match(r"0\d+").fillna(False).sum()),
            "passed": all(c["passed"] for c in checks)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()
    raw_dir = args.raw_dir.expanduser().resolve()
    missing = [name for name in ["product_info.csv", *REVIEW_FILES] if not (raw_dir / name).is_file()]
    if missing:
        parser.error(f"Missing raw CSVs: {missing}")
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    run_dir = (args.run_dir or ROOT / "data/part_a_reruns" / stamp).resolve()
    report_dir = (args.report_dir or ROOT / "results/part_a_validation").resolve()
    if run_dir.exists() or report_dir.exists():
        parser.error("Run/report directories must be new; existing datasets and results will not be overwritten.")
    merged, processed = require_merged(), require_analysis()
    protected = {relative(p): fingerprint(p) for p in [merged, processed, *(raw_dir / n for n in ["product_info.csv", *REVIEW_FILES])]}
    models = [*ROOT.glob("Part B.*/*.ipynb"), *ROOT.glob("Part C.*/*.ipynb"), *ROOT.glob("Part E.*/*.ipynb"),
              *ROOT.glob("Part F.*/Python Scripts/*.py")]
    sources = {relative(p): fingerprint(p) for p in models}
    run_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    evidence = {"protected_inputs": protected, "downstream_sources_before": sources,
                "run_dir": relative(run_dir), "raw_dir": relative(raw_dir), "reference_merged": relative(merged)}
    evidence["pipeline_source"] = fingerprint(ROOT / "Part A./Data_Integration_Audit.ipynb")
    report = report_dir / "comparison.json"
    report.write_text(json.dumps(evidence, indent=2) + "\n")
    env = os.environ.copy()
    env.update({"SEPHORA_RAW_DIR": str(raw_dir), "SEPHORA_DATA_DIR": str(run_dir / "data"),
                "SEPHORA_RESULTS_DIR": str(report_dir)})
    status = subprocess.run([sys.executable, str(ROOT / "scripts/run_analysis.py"), "--parts", "A", "--include-upstream"],
                            cwd=ROOT, env=env)
    evidence["part_a_exit_code"] = status.returncode
    evidence["protected_inputs_unchanged"] = all(fingerprint(ROOT / p) == meta for p, meta in protected.items())
    evidence["downstream_sources_unchanged"] = all(fingerprint(ROOT / p) == meta for p, meta in sources.items())
    report.write_text(json.dumps(evidence, indent=2) + "\n")
    if status.returncode:
        raise SystemExit("Part A failed; see logs. Existing datasets have not been overwritten.")
    rebuilt_path = run_dir / "data/processed/merged_reviews.parquet"
    old, new = pd.read_parquet(merged), pd.read_parquet(rebuilt_path)
    evidence.update({"rebuilt": {"path": relative(rebuilt_path), **fingerprint(rebuilt_path)},
                     "reference_shape": list(old.shape), "rebuilt_shape": list(new.shape),
                     "column_order_equal": list(old.columns) == list(new.columns)})
    columns = []
    for col in old.columns.union(new.columns, sort=False):
        entry = {"column": col, "present_in_both": col in old and col in new}
        if entry["present_in_both"] and len(old) == len(new):
            entry.update({"original_dtype": str(old[col].dtype), "rebuilt_dtype": str(new[col].dtype),
                          "dtype_equal": old[col].dtype == new[col].dtype,
                          "original_missing": int(old[col].isna().sum()), "rebuilt_missing": int(new[col].isna().sum()),
                          "different_values": int((~equal_values(old[col], new[col])).sum())})
        columns.append(entry)
    pd.DataFrame(columns).to_csv(report_dir / "column_comparison.csv", index=False)
    evidence.update({"columns": columns,
                     "exact_value_differences": sum(c.get("different_values", 0) for c in columns),
                     "dtype_differences": [c["column"] for c in columns if not c.get("dtype_equal", False)]})
    evidence["storage_comparison"] = storage_comparison(merged, rebuilt_path)
    evidence["independent_raw_audit"] = independent_audit(raw_dir, new, report_dir)
    evidence["no_significant_issues"] = bool(evidence["reference_shape"] == evidence["rebuilt_shape"]
        and evidence["column_order_equal"] and not evidence["exact_value_differences"]
        and not evidence["dtype_differences"] and evidence["independent_raw_audit"]["passed"]
        and evidence["protected_inputs_unchanged"] and evidence["downstream_sources_unchanged"])
    evidence["difference_classification"] = {
        "analysis_values": ("Exact match across every row and all 46 columns; no observed data discrepancy."
                            if evidence["no_significant_issues"] else "Differences or failed checks require investigation before publication."),
        "serialization": ("Only footer metadata differs; all pre-footer Parquet bytes are identical."
                          if evidence["storage_comparison"]["parquet_data_payload_byte_identical"]
                          else "Parquet payloads differ; compare logical values and investigate storage differences."),
        "code_corrections": "String-ID ingestion and schema/path/audit corrections are assessed separately from data discrepancies.",
        "post_imputation_duplicates": evidence["independent_raw_audit"]["post_imputation_duplicates"],
    }
    report.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: evidence[k] for k in ["reference_shape", "rebuilt_shape", "exact_value_differences",
                     "dtype_differences", "protected_inputs_unchanged", "downstream_sources_unchanged", "no_significant_issues"]}, indent=2))
    print("Independent raw audit:", evidence["independent_raw_audit"]["passed"])
    print("Report:", report)
    raise SystemExit(0 if evidence["no_significant_issues"] else 1)


if __name__ == "__main__":
    main()
