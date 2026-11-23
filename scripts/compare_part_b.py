"""Rerun B in new directories and compare with the authoritative processed file."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_paths import require_analysis, require_merged


def fingerprint(path):
    with path.open("rb") as stream:
        return {"bytes": path.stat().st_size,
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def relative(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def storage_comparison(original, rebuilt):
    """Distinguish Parquet footer/Arrow representation from actual payload changes."""
    old, new = pq.ParquetFile(original), pq.ParquetFile(rebuilt)

    def payload(path, footer_bytes):
        remaining = path.stat().st_size - 8 - footer_bytes
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("Unexpected end of Parquet payload")
                digest.update(chunk)
                remaining -= len(chunk)
        return digest.hexdigest()

    old_payload = payload(original, old.metadata.serialized_size)
    new_payload = payload(rebuilt, new.metadata.serialized_size)
    metadata_old = json.loads(old.schema_arrow.metadata[b"pandas"])
    metadata_new = json.loads(new.schema_arrow.metadata[b"pandas"])
    return {
        "physical_parquet_schema_equal": old.schema.equals(new.schema),
        "arrow_schema_equal": old.schema_arrow.equals(new.schema_arrow, check_metadata=False),
        "arrow_type_differences": [{"column": a.name, "original": str(a.type), "rebuilt": str(b.type)}
                                   for a, b in zip(old.schema_arrow, new.schema_arrow) if not a.equals(b)],
        "original_writer": old.metadata.created_by, "rebuilt_writer": new.metadata.created_by,
        "original_pandas_version": metadata_old["pandas_version"],
        "rebuilt_pandas_version": metadata_new["pandas_version"],
        "original_footer_bytes": old.metadata.serialized_size,
        "rebuilt_footer_bytes": new.metadata.serialized_size,
        "original_payload_sha256": old_payload, "rebuilt_payload_sha256": new_payload,
        "parquet_data_payload_byte_identical": old_payload == new_payload,
    }


def artifact_comparison(report_dir):
    summaries = []
    for name in ["cleaning_log.csv", "feature_dictionary.csv", "feature_selection.csv"]:
        original = next(ROOT.glob("Part B.*/outputs/" + name))
        rebuilt = report_dir / "part_b" / name
        old, new = pd.read_csv(original), pd.read_csv(rebuilt)
        item = {"file": name, "exact_table_match": old.equals(new), "changes": []}
        if old.shape == new.shape and list(old.columns) == list(new.columns):
            for column in old:
                same = old[column].eq(new[column]).fillna(False) | (old[column].isna() & new[column].isna())
                for index in old.index[~same]:
                    item["changes"].append({"row": int(index), "column": column,
                                            "original": str(old.loc[index, column]),
                                            "rebuilt": str(new.loc[index, column])})
        summaries.append(item)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merged", type=Path)
    parser.add_argument("--run-dir", type=Path,
                        help="New directory for rebuilt datasets; must not already exist")
    parser.add_argument("--report-dir", type=Path,
                        help="New directory for reports; must not already exist")
    args = parser.parse_args()
    merged = args.merged.expanduser().resolve() if args.merged else require_merged()
    authoritative = require_analysis()
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    run_dir = (args.run_dir or ROOT / "data/part_b_reruns" / stamp).resolve()
    report_dir = (args.report_dir or ROOT / "results/part_b_validation").resolve()
    if run_dir.exists() or report_dir.exists():
        parser.error("Run/report directories must be new to prevent overwriting previous data or results.")
    protected = {str(p): fingerprint(p) for p in (merged, authoritative)}
    models = [*ROOT.glob("Part C.*/*.ipynb"), *ROOT.glob("Part E.*/*.ipynb"),
              *ROOT.glob("Part F.*/Python Scripts/*.py")]
    model_fingerprints = {relative(p): fingerprint(p) for p in models}
    report_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    evidence = {"merged_input": {"path": relative(merged), **protected[str(merged)]},
                "authoritative_input": {"path": relative(authoritative), **protected[str(authoritative)]},
                "rebuilt_data_dir": relative(run_dir / "data/processed"),
                "report_dir": relative(report_dir), "model_source_before": model_fingerprints}
    report = report_dir / "comparison.json"
    report.write_text(json.dumps(evidence, indent=2) + "\n")
    env = os.environ.copy()
    env.update({"SEPHORA_MERGED_PATH": str(merged), "SEPHORA_DATA_DIR": str(run_dir / "data"),
                "SEPHORA_RESULTS_DIR": str(report_dir)})
    result = subprocess.run([sys.executable, str(ROOT / "scripts/run_analysis.py"),
                             "--parts", "B", "--include-upstream"], cwd=ROOT, env=env)
    evidence["part_b_exit_code"] = result.returncode
    evidence["protected_inputs_unchanged"] = all(fingerprint(Path(p)) == meta for p, meta in protected.items())
    evidence["models_unchanged"] = all(fingerprint(ROOT / p) == meta for p, meta in model_fingerprints.items())
    report.write_text(json.dumps(evidence, indent=2) + "\n")
    if result.returncode:
        raise SystemExit("Part B failed; comparison.json and logs retain the failure. No existing data was overwritten.")
    rebuilt = run_dir / "data/processed/analysis_ready.parquet"
    old, new = pd.read_parquet(authoritative), pd.read_parquet(rebuilt)
    evidence.update({"rebuilt": {"path": relative(rebuilt), **fingerprint(rebuilt)},
                     "original_shape": list(old.shape), "rebuilt_shape": list(new.shape),
                     "column_order_equal": list(old.columns) == list(new.columns),
                     "row_order_equal": old.review_id.equals(new.review_id),
                     "review_id_unique": old.review_id.is_unique and new.review_id.is_unique})
    if not evidence["review_id_unique"]:
        raise ValueError("Review IDs must be unique before row alignment")
    old, new = old.set_index("review_id", drop=False), new.set_index("review_id", drop=False)
    only_old, only_new = old.index.difference(new.index), new.index.difference(old.index)
    common_ids = old.index.intersection(new.index)
    new = new.reindex(common_ids)
    old = old.reindex(common_ids)
    evidence.update({"review_ids_only_original": len(only_old), "review_ids_only_rebuilt": len(only_new),
                     "shared_review_ids": len(common_ids)})
    columns = []
    for col in old.columns.union(new.columns, sort=False):
        entry = {"column": col, "present_in_both": col in old and col in new}
        if not entry["present_in_both"]:
            columns.append(entry)
            continue
        left, right = old[col], new[col]
        both_missing = left.isna() & right.isna()
        # Compare categorical values separately from reference order metadata.
        if isinstance(left.dtype, pd.CategoricalDtype):
            same = left.astype(object).eq(right.astype(object)).fillna(False) | both_missing
        else:
            same = left.eq(right).fillna(False) | both_missing
        entry.update({"original_dtype": str(left.dtype), "rebuilt_dtype": str(right.dtype),
                      "dtype_equal": left.dtype == right.dtype,
                      "original_missing": int(left.isna().sum()), "rebuilt_missing": int(right.isna().sum()),
                      "different_values_exact": int((~same).sum()),
                      "significant_differences": int((~same).sum())})
        if isinstance(left.dtype, pd.CategoricalDtype) and isinstance(right.dtype, pd.CategoricalDtype):
            entry["category_metadata_equal"] = (list(left.cat.categories) == list(right.cat.categories)
                                                 and left.cat.ordered == right.cat.ordered)
        if pd.api.types.is_float_dtype(left) and pd.api.types.is_float_dtype(right):
            values_left, values_right = left.to_numpy(dtype=float), right.to_numpy(dtype=float)
            entry["max_abs_difference"] = float(np.nanmax(np.abs(values_left - values_right)))
            entry["significant_differences"] = int((~np.isclose(values_left, values_right,
                                                               rtol=1e-12, atol=1e-12, equal_nan=True)).sum())
        columns.append(entry)
    pd.DataFrame(columns).to_csv(report_dir / "column_comparison.csv", index=False)
    evidence.update({"columns": columns, "exact_value_differences": sum(c.get("different_values_exact", 0) for c in columns),
                     "significant_value_differences": sum(c.get("significant_differences", 0) for c in columns),
                     "dtype_differences": [c["column"] for c in columns if not c.get("dtype_equal", False)],
                     "category_metadata_differences": [c["column"] for c in columns if not c.get("category_metadata_equal", True)]})
    evidence["storage_comparison"] = storage_comparison(authoritative, rebuilt)
    evidence["artifact_comparison"] = artifact_comparison(report_dir)
    evidence["no_significant_issues"] = bool(
        evidence["protected_inputs_unchanged"] and evidence["models_unchanged"]
        and evidence["original_shape"] == evidence["rebuilt_shape"]
        and evidence["column_order_equal"] and evidence["row_order_equal"]
        and not len(only_old) and not len(only_new)
        and not evidence["dtype_differences"] and not evidence["category_metadata_differences"]
        and not evidence["significant_value_differences"])
    report.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: evidence[k] for k in ["original_shape", "rebuilt_shape", "row_order_equal",
                     "column_order_equal", "exact_value_differences", "significant_value_differences",
                     "dtype_differences", "category_metadata_differences", "protected_inputs_unchanged",
                     "models_unchanged", "no_significant_issues"]}, indent=2))
    print(f"Comparison evidence: {report}")
    raise SystemExit(0 if evidence["no_significant_issues"] else 1)


if __name__ == "__main__":
    main()
