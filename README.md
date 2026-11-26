# Sephora skincare review analysis

STAT5106 research project on associations between product characteristics, reviewer skin type, five-star ratings and recommendations. The analysis uses 1,093,847 reviews of 2,351 products from the March 2023 Sephora US snapshot.

## Repository structure

```text
part_a_data_integration/          01_data_integration.ipynb
part_b_data_cleaning/             02_data_cleaning.ipynb
part_c_exploratory_analysis/      03_exploratory_analysis.ipynb
part_d_statistical_uncertainty/   04_statistical_uncertainty.ipynb + ANALYSIS_NOTES.md
part_e_main_modeling/             05_main_modeling.ipynb
part_f_secondary_analysis/        recommendation_analysis.py
                                 log_price_sensitivity.py
                                 model_comparison.py + ANALYSIS_NOTES.md
scripts/                         run_pipeline.py, validate_results.py
project_paths.py
requirements.txt
requirements-lock.txt
```

Each part has one `outputs/` directory. Figures are in `outputs/figures/`. A/B outputs document integration and feature definitions; C contains descriptive tables, D contains cluster-bootstrap intervals, E contains adjusted model estimates/evaluation and generated `outputs/analysis_notes.md`, and F contains secondary/sensitivity results. Only final analysis code, results and analytical notes are tracked.

## Data

Source: [Sephora Products and Skincare Reviews on Kaggle](https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews). Download and extract the six original CSVs manually:

```text
data/raw/
  product_info.csv
  reviews_0-250.csv
  reviews_250-500.csv
  reviews_500-750.csv
  reviews_750-1250.csv
  reviews_1250-end.csv
```

A produces `data/processed/merged_reviews.parquet` (~219 MB); B produces `data/processed/analysis_ready.parquet` (~19 MB, 1,093,847 × 52). **The B processed file is the authoritative input for C–F.** Place an existing copy there or set `SEPHORA_ANALYSIS_PATH=/absolute/path/analysis_ready.parquet`. A/B can generate it from the original CSVs; C–F do not need the raw CSVs or merged file.

All datasets, including the processed Parquet and optional text lookup, are intentionally excluded from Git. An absent intermediate in a checkout is expected. Nothing is automatically downloaded.

## Reproduce

The tested environment is Python 3.14.6. Install the pinned versions to match it:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/run_pipeline.py
python scripts/validate_results.py
```

The default order is **C → E → D → F**: D uses E's saved predictions. All three F scripts run. The runner refits models, regenerates final outputs, checks failures/convergence and confirms the processed input remains unchanged. The validator independently checks descriptive statistics, product-multiplicity bootstrap intervals, model-result identities, interpretation labels and product-disjoint evaluation. It uses only current data/code/results, with no external history or backup files. Logs, executed notebook copies and run metadata stay locally in ignored `.run/`.

To rerun a subset, use `python scripts/run_pipeline.py --parts E D`. Notebooks also run interactively from within this checkout. `SEPHORA_RESULTS_DIR` optionally selects an alternate output root with the same part-folder layout.

To build A/B first, use a **new** data directory and the extracted CSV location:

```bash
SEPHORA_RAW_DIR=/absolute/path/to/csvs \
SEPHORA_DATA_DIR=/absolute/path/to/new-data \
python scripts/run_pipeline.py --parts A B --include-upstream

SEPHORA_ANALYSIS_PATH=/absolute/path/to/new-data/processed/analysis_ready.parquet \
python scripts/run_pipeline.py
SEPHORA_ANALYSIS_PATH=/absolute/path/to/new-data/processed/analysis_ready.parquet \
python scripts/validate_results.py
```

A/B are opt-in and refuse to overwrite existing Parquet outputs. `SEPHORA_MERGED_PATH` can select an existing intermediate for B. On another Python version (code requires 3.11+), install `requirements.txt` and validate package/platform compatibility.

## Interpretation

- **C/D are unadjusted and descriptive.** D uses 2,000 product-cluster bootstrap replicates, seed 5106, review-weighted ratios and paired percentile intervals. Intervals are pointwise, without multiplicity correction; `boot_p` values are percentile-tail approximations.
- **E/F are adjusted logistic models**, with product-clustered standard errors. Categorical reference groups are **Budget price, Normal skin and Moisturizers**. In interaction models, main price odds ratios are **conditional on Normal skin**; main skin-type odds ratios are conditional on Budget price. E's reduced model has no price × skin interaction. In F's log-price model, the main price slope is for Normal skin; a doubling multiplies log price by `ln(2)`. Skin coefficients in that model refer to `log_price = 0` ($1).
- **D and E test different interaction hypotheses.** D compares unadjusted Luxury-minus-Budget risk differences across four reported skin types, excluding Not reported. E jointly tests 12 adjusted log-odds interactions across all price bands and all five skin groups. Their p-values are not interchangeable.
- E's predictions average over a common covariate mix and are not raw cell rates. Interval overlap does not establish equivalence. F's recommendation outcome uses 926,031 observed-response rows; its five-star refit uses those same rows for comparison.
- Model evaluation uses 80/20 product-disjoint splits, seed 5106, with thresholds 0.5 and the training outcome rate. Globally prepared category/highlight choices and author attribute fills limit prospective interpretation. Product snapshots may not describe historical review-time characteristics; dependence across products sharing authors/brands remains possible. Findings are observational, not causal.

See D's and F's analytical notes and E's generated notes for report/slide-ready results and limitations. The notebooks retain their supplied AI-use acknowledgements where applicable.

### Skin-type reporting check

Part C includes a reproducible check of the processed `Not reported` skin-type group. Run the C notebook or `python part_c_exploratory_analysis/skin_type_reporting.py`. Three CSVs in C's `outputs/` give annual shares, author activity and five-star rates before 2017 versus from 2017, with explicit expectation-comparison columns.

Author review totals are counted over the **full dataset before any grouping**. The review-weighted medians are 1 (Not reported) versus 3 (Reported); counting each distinct author once within a reporting group gives 1 versus 1. Authors can appear in both groups. Annual shares are 29.34–51.35% in 2012–2017 and below 2% in 2018–2022, but **2023 is 5.95%** (all 2018-onward reviews pooled: 1.26%). The four period rates round to 67.5%/66.5% before 2017 and 63.7%/63.4% from 2017. These are descriptive patterns, not adjusted effects or a statement about missingness in the original raw CSVs.

### Main-effects collinearity check

Part E's notebook and `python part_e_main_modeling/collinearity.py` generate `part_e_main_modeling/outputs/vif_main_effects.csv` using statsmodels `variance_inflation_factor` on all analysis reviews. The design matches the reduced model, with Budget / Normal / Moisturizers reference levels. The intercept is retained in auxiliary regressions and omitted from the table. Interaction terms are excluded because product terms induce high VIFs by construction; the check describes the main-effects design. `scripts/validate_results.py` independently verifies the coding, sample size and values using the inverse centred correlation matrix, and checks the expected VIFs below 2.5.
