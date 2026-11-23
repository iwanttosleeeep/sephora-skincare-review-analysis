# Sephora skincare review analysis

This project studies how product price, category, marketing claims and reviewer skin type relate to five-star skincare reviews and recommendations. The source is the public Kaggle dataset [Sephora Products and Skincare Reviews](https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews), collected from Sephora's US website in March 2023.

## Data and pipeline status

| Part | Purpose | Input → output | Availability / verification |
| --- | --- | --- | --- |
| A | Integrate and audit | Product catalogue + five review CSVs → `merged_reviews.parquet` | Rerun in isolation; all 1,093,970 × 46 values match; 49 independent raw-data checks passed |
| B | Clean and engineer features | `merged_reviews.parquet` → `analysis_ready.parquet` | Rerun in isolation; all 1,093,847 × 52 values, dtypes and categories match the supplied processed file |
| C | Exploratory analysis | `analysis_ready.parquet` → tables and figures | Rerun with supplied processed file |
| D | Additional statistical analysis | `analysis_ready.parquet` | Pending; will be added later |
| E | Main models and evaluation | `analysis_ready.parquet` → clustered odds ratios, metrics and figures | Rerun with supplied processed file |
| F | Secondary outcome and sensitivity | `analysis_ready.parquet` → recommendation/log-price models and comparison tables | All three scripts rerun |

**The authoritative downstream input is** `Part B. Data Cleaning & Feature Engineering/data/processed/analysis_ready.parquet`: 19,002,351 bytes (~19 MB), 1,093,847 rows × 52 columns, 2,351 products. All C–F analyses should use this file through `project_paths.require_analysis()`.

**Datasets are intentionally omitted from Git, including `merged_reviews.parquet` (~219 MB) and `analysis_ready.parquet` (~19 MB). Their absence from a checkout is expected, not a project error.** Supply the authoritative processed file manually at the path above, or set `SEPHORA_ANALYSIS_PATH`. No data is automatically downloaded or regenerated.

For the 2026-11-23 checks, the supplied merged file was available locally at `Part A./merged_reviews.parquet`, and the six original CSVs were subsequently supplied in local `archive/`. The merged file is needed only to rerun B, not C–F. The optional text lookup was regenerated inside the ignored B rerun directory. All these datasets remain excluded from Git.

## Run the available analyses

From this project folder, use Python 3.14 to match the verified environment (3.14.6). Tested package versions are in `requirements-lock.txt` and `results/environment.json`. For another Python version supporting the code (3.11+), install `requirements.txt` instead of the locked versions and rerun verification; package/platform compatibility must be checked for that environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/run_analysis.py
python scripts/verify_results.py
python scripts/check_upstream_helpers.py
```

`run_analysis.py` defaults to C, E and all three F scripts. It runs each notebook/script in a separate process, checks failures and model convergence, and confirms the input hash is unchanged. No Jupyter server is needed. Notebooks can also be opened interactively with this environment; run them from within the project folder or a Part folder.

Regenerated results go to `results/part_c/`, `results/part_e/` and `results/part_f/`. The supplied result files remain in their original Part folders. Execution logs and executed notebook copies are under `results/logs/` and `results/executed/` and are ignored by Git. Headless runs save PNG files; Matplotlib may also print a non-interactive-display warning.

To run a subset, use `python scripts/run_analysis.py --parts C E` (the verification command expects a complete default C/E/F run). Paths are resolved within this project rather than through Windows drives or a search of the user's home directory. To use an externally stored processed file:

```bash
export SEPHORA_ANALYSIS_PATH="/absolute/path/to/analysis_ready.parquet"
python scripts/run_analysis.py
```

`SEPHORA_RESULTS_DIR` optionally changes the result directory. Verification compares the supplied dataset fingerprint and original results, so a deliberately different dataset requires a new, separately documented validation baseline.

## Safely rerun and compare Part A

With the six CSVs and existing reference datasets available locally:

```bash
python scripts/compare_part_a.py --raw-dir archive
```

The script executes the corrected A notebook into a new `data/part_a_reruns/<timestamp>/` directory and compares every row and column with the existing merged file. It separately verifies raw review fields, lexical IDs, duplicate removal, same-author imputation and every product join field against the CSVs. It checks raw/reference data and B/C/E/F source fingerprints; downstream models are not executed or changed.

Compact reports go to `results/part_a_validation/`; existing run/report directories are rejected. Use a new `--report-dir` and optionally `--run-dir` for another check. `SEPHORA_RAW_DIR` also supports an external CSV directory for direct notebook execution.

The completed comparison found zero data differences. The only file difference is harmless footer metadata; two expected post-imputation duplicates also match the reference and are handled by B. See [A's comparison evidence](results/part_a_validation/comparison.json) and [the review](docs/REVIEW.md).

## Safely rerun and compare Part B

With both the merged input and authoritative processed file available locally:

```bash
python scripts/compare_part_b.py --merged "Part A./merged_reviews.parquet"
```

This runs the existing B notebook in a fresh `data/part_b_reruns/<timestamp>/` directory and compares all rows and columns with the existing authoritative file. It verifies input and model-source fingerprints, row/column order, missingness, pandas dtypes, categories, exact values, and Parquet storage differences. It does not run or alter C/E/F models. Reports and B's compact outputs go to `results/part_b_validation/`; raw text, rebuilt Parquet files, logs and executed notebook copies remain excluded from Git.

Existing run/report directories are rejected. To repeat the check without overwriting previous outputs, supply a new `--report-dir` (and optionally a new `--run-dir`). `SEPHORA_MERGED_PATH` can also select an externally stored merged file.

The completed comparison found **zero differing values**, no changed dtypes or category metadata, and no changed row/column order. A footer-only serialization difference is documented in [the B comparison evidence](results/part_b_validation/comparison.json) and [the review](docs/REVIEW.md).

## Rerun the complete available pipeline later

Only do this after manually obtaining the original inputs. Keep large inputs outside GitHub, for example:

```text
/absolute/path/sephora-data/
  raw/
    product_info.csv
    reviews_0-250.csv
    reviews_250-500.csv
    reviews_500-750.csv
    reviews_750-1250.csv
    reviews_1250-end.csv
  processed/
```

```bash
export SEPHORA_DATA_DIR="/absolute/path/sephora-data"
python scripts/run_analysis.py --parts A B --include-upstream
# B writes the rebuilt file to the external processed/ directory.
# Select it explicitly to rerun downstream analysis:
export SEPHORA_ANALYSIS_PATH="$SEPHORA_DATA_DIR/processed/analysis_ready.parquet"
python scripts/run_analysis.py
```

The explicit `--include-upstream` flag is required for A/B. A validates that all six files exist before loading; B explains the missing intermediate if it is unavailable. B rebuilds into `SEPHORA_DATA_DIR/processed/`, preserving the supplied authoritative file. Without the environment override, upstream data defaults to the ignored root `data/` folder. D will need to be integrated when its code is supplied.

## Preservation, checks and interpretation

Before corrections, the original notebooks, F scripts and all supplied manageable results were copied byte-for-byte into `preservation/original_notebooks_and_results.zip`. `preservation/manifest.json` records SHA-256 hashes and file sizes, including the processed Parquet file, which was fingerprinted in place rather than duplicated. Corrected source notebooks have cleared outputs; executed copies are separate so old outputs cannot be mistaken for new runs.

See [the code review](docs/REVIEW.md), [machine-readable downstream checks](results/verification.json), [C/E/F result comparisons](results/result_comparison.csv), [A's column comparisons](results/part_a_validation/column_comparison.csv), and [B's column comparisons](results/part_b_validation/column_comparison.csv). A/B/C/E/F verification includes execution. Separate A and B reruns reproduce the raw-to-merged and merged-to-processed stages without replacing the existing reference files.

Models use product-clustered standard errors and product-disjoint evaluation with seed 5106. Their associations are observational. The main model's held-out ROC-AUC is about 0.524 and its joint price × skin interaction p-value is about 0.5005. Global preprocessing, author attribute filling across products, and 2023 product snapshots applied to older reviews limit prospective interpretations; see the review report.

## Repository file policy

Keep source code, notebooks, documentation, CSV summaries, compact PNGs and the preservation archives. `.gitignore` excludes **all Parquet datasets**, raw-data directories, text lookup files, caches, fitted-model binaries, logs, executed notebook copies and local environments. Do not add datasets inside archives; existing tracked files require explicit removal from Git's index because ignore rules do not untrack them.
