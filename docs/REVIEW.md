# Code review and reproducibility verification

Review date: 2026-11-23 (Asia/Hong_Kong).

## Scope and preservation

The supplied `analysis_ready.parquet` is the authoritative input. The initial review did not execute A/B because upstream inputs were unavailable. In the 2026-11-23 follow-up below, B was executed using the newly supplied merged file. No Kaggle download, A execution, or intermediate reconstruction was performed. Part D is pending. Raw-to-merged provenance remains unverified without the original CSVs.

Before source edits, 57 supplied files were fingerprinted in `preservation/manifest.json`. Original notebooks, F scripts and results (56 files) are stored in `preservation/original_notebooks_and_results.zip`. The ~19 MB processed dataset was fingerprinted in place and remains unchanged. The verification script checks every archived file against its pre-edit hash. Supplied result files remain in their original locations; new results are separate.

## Follow-up: Part B rerun from the supplied merged file

**Outcome: no significant issues found; the rebuilt dataset matches the authoritative data exactly at the pandas analysis level.** The complete B notebook executed successfully, including all integrity, encoding, model-readiness and Parquet readback assertions. No C/E/F model was changed or refitted during this follow-up.

The new input was `Part A./merged_reviews.parquet`: 219,310,137 bytes, 1,093,970 rows × 46 columns, SHA-256 `8bb2f5ace440e2b3fbeddf4950222e61a36a67624e3d80926b4e1fab21083e2e`. B removed 2 exact duplicates introduced after author-attribute filling and 121 same-author/product/date near-identical resubmissions, leaving 1,093,847 rows × 52 columns.

`scripts/compare_part_b.py` ran the existing notebook into the new ignored directory `data/part_b_reruns/20261123T214256+0800/data/processed/`. Compact outputs and reports were written separately under `results/part_b_validation/`, leaving the original Part B outputs and previous C/E/F verification evidence intact. Its fresh-directory guards reject an existing run or report directory. Explicit `SEPHORA_MERGED_PATH` support and the actual `Part A./merged_reviews.parquet` location were added to path resolution; the cleaning and modeling specifications were unchanged.

| Comparison | Result |
| --- | --- |
| Review IDs and membership | Same 1,093,847 unique IDs; none added or removed |
| Row order / column names and order | Identical |
| Values | Zero differences across all 52 columns, including outcomes, predictors, identifiers and dates |
| Missingness / pandas dtypes | Identical |
| Category levels, order and ordered flags | Identical, including reference levels |
| Feature dictionary / feature selection | Exact CSV table matches |
| Cleaning log | All row counts and decisions match; only the explanatory text `All 7 checks passed` became `All integrity checks passed`, reflecting the earlier added author-ID check |
| Physical Parquet schema / data payload | Same physical schema and byte-identical data payload |
| Original input files / C/E/F model sources | Before/after hashes unchanged |

The rebuilt Parquet has SHA-256 `18427b685677e77f024979a3c6b776a54b800fd1cdca3c98caaa8cf664dc5be6` and is 19,002,333 bytes, compared with 19,002,351 bytes for the authoritative file (`c0ef6e2cc2f50d2267820d8da0f0c545e0761b2d7726bca27331b70cac9eea73`). This is a **footer-only serialization difference**, not changed analysis data: the pre-footer data payload has the same SHA-256 in both files. The original writer metadata records PyArrow 25.0.1 / pandas 2.2.3, versus PyArrow 26.0.1 / pandas 3.0.6 for the rerun. Arrow footer types for six text columns changed from `string` to `large_string` and their pandas metadata from `unicode` to `object`; both load into identical pandas string dtypes and contain identical values. The physical Parquet schema is unchanged. No data repair or replacement is warranted.

Evidence: `results/part_b_validation/comparison.json`, `column_comparison.csv`, `execution.json`, and compact B outputs under `part_b/`. The pre-follow-up source snapshot and input/model fingerprints are preserved in `preservation/part_b_rerun_before.zip` and `preservation/part_b_rerun_before.json`. The original merged and processed files were never overwritten. `.gitignore` now excludes every Parquet dataset, including the original processed file and regenerated text lookup; only code, documentation, preservation snapshots and manageable results are eligible for publication.

This establishes reproducibility from the supplied merged file to the authoritative processed dataset. It does not independently validate A's processing of the unavailable raw CSVs or resolve the observational/prospective limitations below.

## A: integration and audit — static review

The left join uses `validate="many_to_one"`, rejects missing/duplicate product keys, retains unmatched reviews with an audit flag, and asserts the join preserves the number of review rows. Duplicate handling excludes feedback counts and file provenance; consistent-author imputation is restricted to authors with exactly one observed attribute value. These are coherent retrospective integration rules.

Corrections made:

- Input IDs are read as strings at CSV ingestion to prevent numeric inference from changing reviewer IDs before later conversion to strings.
- The raw directory is explicit and configurable; all six files must exist, and a schema mismatch between review files stops concatenation.
- Audit tables are now saved to `results/part_a/`; previously the heading promised saved reports but the code saved only Parquet.
- Shared paths remove dependence on the notebook launch directory.

Limitations: no raw files were available to test the join, coercion audit, demographic fills, deduplication, or original row counts. Case-insensitive author comparisons preserve the first original spelling; current B mappings expect the source spelling. Future new raw exports may require explicit normalization. The post-imputation duplicate pass in B is retained because filling attributes can make rows identical. A's left join cannot count catalogue products without reviews through the `right_only` indicator; a separate anti-join would be needed for that different question.

## B: cleaning and feature engineering — initial static review

Fixed price cutoffs, explicit reference categories, separate outcomes, leakage exclusions, product-variable constancy checks and Parquet readback checks are appropriate for the stated downstream models. The supplied processed data is independently checked for IDs, ratings, outcomes, fixed price bins, log transforms, dummy encoding, product-variable constancy, interaction-cell coverage, dates and repeat-author counts.

Corrections made:

- B resolves the actual `Part A.` layout and explicitly documents the absent intermediate. Rebuilds write into the external/ignored data directory, preserving the supplied processed file.
- Ratings must be one of the five integer values before conversion to `int8`; the old `between(1, 5)` test would also admit fractional ratings.
- Missing author IDs fail early with a clear integrity check rather than failing during grouped counts converted to `int16`.
- Two empty/missing review texts alone no longer qualify as near-identical resubmissions.
- Highlight parsing rejects malformed values or non-list/non-string content rather than silently treating parse failures as missing or iterating over a string.
- External paths no longer fail at relative-path printing.
- The preprocessing documentation now states the limits of its leakage claim.

Residual analytical decisions: same-day text deduplication can drop a near-identical review with a different rating, and its similarity threshold of 0.9 remains a study choice. The follow-up reproduces that decision from the supplied intermediate; it does not independently establish which reviews represent resubmissions. The source's pre-2017 recommendation missingness pattern is verified, but an absent historical field is an interpretation of that pattern, not independently established website history.

## C: exploratory analysis — execution review

C uses all 1,093,847 processed reviews and checks `five_star == (rating == 5)`. Both review counts and unique-product coverage are retained. It now reads the shared authoritative path, does not install dependencies inside the notebook, and does not recursively search the user's home directory. Placeholder citation markers without sources were removed. The accidental extensionless duplicate category export was removed; its original bytes remain preserved. Producing code was added for the three supplied Step 3 CSVs, which were previously present without corresponding notebook code.

Original narrative findings are compared against regenerated summaries rather than treated as independently measured results. The original AI-use statement was qualified to distinguish the author's work from this reproducibility review; final report integration is not claimed by this review.

## E: main models and held-out evaluation — execution review

The main specification has 37 parameters and the reduced specification 25. Full-data fits estimate associations with product-clustered covariance. Evaluation refits on training products only, with an 80/20 product split and seed 5106. Thresholds are 0.5 and the training five-star rate; test outcomes are not used to choose the threshold. Outcome-derived fields and snapshot flags are excluded as predictors.

Corrections made:

- Shared input/output paths replace launch-directory assumptions.
- Model fitting rejects missing model values and raises if optimization does not converge.
- Scenario predictions distinguish Patsy `DesignInfo` from Formulaic `ModelSpec`. The original code passed `model_spec` directly to Patsy's design-matrix builder, which is incompatible with a Formulaic specification and relies on a version-dependent attribute under older statsmodels.
- Weighted unique covariate rows reproduce the sampled 50,000-row average without allocating a 50,000 × 500 simulation matrix in each scenario. The original sample size, seed, 500 coefficient draws and interval definition remain unchanged.
- The joint Wald result is exported as CSV; section references and preprocessing scope are clarified.

The predicted-probability intervals reflect coefficient uncertainty conditional on the sampled covariate mix; they do not include uncertainty from estimating that mix. Scenario predictions can combine product claims/category with a price band not observed for a given product. They describe adjusted associations, not interventions or causal effects.

## F: secondary outcome and log-price sensitivity — execution review

All three supplied scripts are executed. The secondary outcome uses the 926,031 rows with observed `recommended`; the five-star model is refit on exactly those rows for comparison. The log-price model replaces price segment, retaining the skin interaction. Models use product-clustered covariance; evaluation uses disjoint products and a training-only threshold. The comparison script independently refits the reported models, providing a consistency check.

Corrections made:

- Removed the hard-coded `D:\\analysis_ready.parquet` path from all three scripts.
- Added missing-value/convergence failures, and a product-disjointness assertion to the comparison script.
- The short log-price summary tables now explicitly state that the main log-price odds ratio and its per-doubling transformation refer to **Normal skin**, because the model includes a log-price × skin interaction.

F currently implements the recommendation and log-price checks. The recent-review subset and removal of repeated-author reviews mentioned as possible checks in B are not implemented by the supplied F scripts and are not claimed as completed analyses. Recommendation-model and full-sample evaluation use different eligible product sets; their AUCs are descriptive comparisons across different outcomes/samples, not a paired model superiority test.

## Interpretation limits

Product-disjoint fitting does not itself establish prospective preprocessing isolation. Category merging and highlight selection were informed by the full predictor distribution, and A imputes author characteristics using other reviews across products before splitting. No outcome is used directly in these predictors, but a future prospective analysis should determine learned choices using training products and restrict author information to what was available at prediction time.

Product prices and claims are March 2023 snapshots attached to reviews from earlier years. Standard errors account for dependence within products, but not all dependence across products sharing authors or brands. These limits do not invalidate reproduction of the supplied analyses; they constrain predictive and causal claims.

## Verification evidence

The exact input fingerprint, environment, execution statuses, dataset checks, product splits and file-by-file numeric comparisons are saved under `results/`. `verify_results.py` exits nonzero if an expected file is absent, an input invariant fails, or a saved result does not reproduce. It compares against the immutable pre-edit archive, not against recently overwritten baselines.

CSV numerical values use absolute/relative tolerance 1e-6, with integer and Boolean columns checked exactly. The same tolerance applies to scenario point estimates and simulated interval endpoints. The actual maximum differences are recorded for every file. The clarified skin-reference text in two log-price summary tables is intentionally excluded from comparison; numerical values remain checked.

See `results/verification.json` for the completed run's outcome and `results/result_comparison.csv` for every supplied C/E/F CSV. No supplied result baseline is automatically updated.

Completed run: all 31 supplied C/E/F CSVs reproduced. All 12 C tables matched exactly. Main-model held-out AUC was 0.5237122613; interaction χ²(12) = 11.3345, p = 0.5005. Recommendation-model AUC was approximately 0.551 and log-price-model AUC approximately 0.518. The largest numeric difference across compared files was approximately 1.32e-8. All fitted models converged. The full-sample split contained 884,579 training and 209,268 test reviews (1,880 and 471 products); the recommendation split contained 746,983 training and 179,048 test reviews. The generated E probability figure was also visually inspected.

`python scripts/check_upstream_helpers.py` additionally checks isolated A/B helpers against synthetic cases: exact numeric-looking IDs, string normalization, fractional numeric preservation, Boolean coercion, malformed highlight input and missing-text deduplication. This does not execute either upstream notebook or establish end-to-end correctness without real inputs.
