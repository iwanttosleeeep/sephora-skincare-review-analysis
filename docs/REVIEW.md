# Code review and reproducibility verification

Initial review: 2026-11-23; Part D follow-up: 2026-11-24 (Asia/Hong_Kong).

## Scope and preservation

The supplied `analysis_ready.parquet` is the authoritative input. The initial review did not execute A/B because upstream inputs were unavailable. Subsequent 2026-11-23 checks executed B from the supplied merged file, then A from the six CSVs downloaded by the user. Both reproduce the existing analysis data exactly. The agent performed no Kaggle download, and every rerun used fresh output directories. Downstream models were not changed or refitted during these upstream checks. Part D was added and audited on 2026-11-24; its findings and corrections are documented below.

Before source edits, 57 supplied files were fingerprinted in `preservation/manifest.json`. Original notebooks, F scripts and results (56 files) are stored in `preservation/original_notebooks_and_results.zip`. The ~19 MB processed dataset was fingerprinted in place and remains unchanged. The verification script checks every archived file against its pre-edit hash. Supplied result files remain in their original locations; new results are separate.

## Part D audit and reproduction on 2026-11-24

**Verification passes after technical corrections: all 101 independent checks pass.** All seven submitted numerical CSVs reproduce, including all bootstrap confidence intervals and the interaction test. The prior 31 C/E/F CSV comparisons also still pass. The original 17-file submission (notebook, notes, CSVs, five figures, HTML and Word draft) is preserved byte-for-byte in `preservation/part_d_original_submission.zip`; `part_d_original_manifest.json` records hashes. The supplied `outputs/`, HTML and Word draft remain historical snapshots. Corrected source/notes are in the Part D folder; current tables, diagnostics, figures and verification evidence are in `results/part_d/`.

The original notebook was first executed with **path-only substitutions**, into `results/part_d_original_rerun/part_d/`, before any statistical corrections. `scripts/reproduce_original_part_d.py --output-dir <new-directory>` reproduces that step from the immutable archive. Corrected D runs through `scripts/run_analysis.py --parts D`; its separate `results/execution_d.json` preserves C/E/F's previous execution record. The full default order is C, E, D, F so E's comparison artifact is ready. No A/B/C/E/F notebook, F model script, supplied model result or authoritative data file was changed or refitted during this audit; protected hashes are in `preservation/part_d_pre_verification.json`.

### Bootstrap methodology and independent checks

The method resamples **2,351 products with replacement for each of 2,000 draws**, seed 5106. Every selected product contributes all its reviews, including full multiplicity if drawn repeatedly. The target is a **review-weighted ratio of sums**, not an equal-product mean. A single draw matrix is reused for overall rates, group rates, cells and all differences, preserving dependence in paired contrasts. Percentile endpoints are 2.5% and 97.5% with linear interpolation; SEs use `ddof=1`. These choices, including the four-reported-skin interaction test, were retained.

`verify_part_d.py` independently constructs dense product multiplicity counts, obtains product/group totals via integer coding and `bincount`, and recomputes rates using matrix multiplication. Explicit sorted order-statistic interpolation independently checks the percentile endpoints. Every group and all 20 cells have positive denominators in all 2,000 draws. An unequal-cluster toy example matches literal review-row expansion, including repeated products; empty-group draws raise an explicit error. The script independently verifies naive Wilson intervals against SciPy, pooled naive normal tests, paired differences, flags, SEs, variance ratios, ICC sums of squares, and the recentred range statistic with its plus-one correction.

The cluster-pairs resampling logic follows [Cameron and Miller's description](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_Cluster_Robust_October152013.pdf). Percentile intervals and shared-index paired resampling follow the definitions in [SciPy's bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). These sources support the computational method, not a claim that the observed catalogue is a random sample.

### Confirmed errors corrected without changing analytical decisions

| Issue | Correction and impact |
| --- | --- |
| ICC uses the unweighted mean of product means for between-product sums of squares and `(n-1)p(1-p)` within products | Use the review-weighted grand mean and binary within-product sum `np(1-p)`. ICC changes from 0.0493741061 to **0.0490411252**. The bootstrap does not depend on this diagnostic, so no intervals change. |
| “All reviews” displays the mean of four segment rates | Correct **63.2447% → 63.8600%**. Equal-product overall is 63.1063%; the weighting estimands are different. |
| Claims Luxury is highest with equal-product weights | **Premium is highest (64.9865%)**; Luxury is second (64.0999%). The ordering still differs from review weighting, where Luxury is lowest. |
| Six of nine category contrasts claimed to exclude zero | Correct count is **five**, using the submitted pointwise paired-difference intervals. |
| Reported skin types described as unrelated because marginal intervals overlap | Oily minus overall is **−0.9607 pp, CI −1.3394 to −0.5976**. Correlated, paired contrasts can be precise despite overlapping marginal intervals. |
| “Five comparisons stop being significant” | Five naive flags fall to one bootstrap flag: **four** lose nominal significance. |
| D said to exclude Not reported “as in E”; test described as one-degree-of-freedom style | E includes all five types. D compares four Luxury-minus-Budget risk differences (three equality restrictions); E tests 12 adjusted log-odds interactions. Neither analytical choice was changed. |
| Interval overlap called equivalence/independent model validation | D compares raw cells with E's adjusted standardized predictions using the same reviews. The comparison is descriptive, not an equivalence test or external validation. |
| Fixed plot limits truncate Oily/Luxury's lower bound and Not reported/Budget's upper bound; D3 connector uses wrong axis | Dynamic bounds include complete intervals in D2/D5; D3 uses a horizontal connector. Titles no longer claim equivalence or population effects. |
| Universal 200-review cap and negligible BCa differences asserted without support | Data reach **16,115** reviews per product. No universal 200 cap is supported. BCa/studentized results were not computed, so their differences cannot be promised small. |

Machine-specific paths and silent omission of the E comparison were replaced by shared project paths and an explicit missing-artifact failure. Input, outcome, fixed levels and product-level grouping invariants are checked. Figures were visually inspected after regeneration. The original Word draft was rendered and all four pages inspected; it and the original HTML were deliberately retained unchanged as labelled historical artifacts, not updated final submission exports.

### Findings and consistency with C E and F

The overall five-star rate is **63.8600%, 95% CI 63.0818–64.6181%**. Bootstrap SE is 0.398128 pp versus naive 0.045934 pp; their variance ratio is 75.1251. The equivalent 14,560 independent reviews applies to this estimator/variance comparison and is not a universal effective sample size. Price pair comparisons retain five naive versus one nominal bootstrap exclusion. Cleansers, Eye Care, Masks, Sunscreen and Tools/Wellness/Self-Tan are the five category contrasts excluding zero; Lip Care's interval includes zero despite the highest point estimate.

C agrees on every count and rate, including all 20 skin × price cells. D's observed/model CSV agrees with E's saved predictions to floating-point tolerance (maximum discrepancy about 1.5e-12 percentage points). E and F agree on their shared full-sample five-star Wald/AUC references. F's recommendation outcome and 926,031-row eligible sample are different from D's all-review five-star analysis and are not direct rate benchmarks.

D's retained range test has **T = 1.599222 pp, p = 0.194403**, Monte Carlo SE approximately **0.00885**. E's 12-term Wald p is **0.500491**. Both fail to reject their respective nulls at 5%, but the scales, contrasts and included skin levels differ; agreement does not establish absence of all interactions. E's Not reported odds ratio is conditional on Budget price, not an overall marginal risk difference.

### Substantive limitations remaining

Intervals are **pointwise and unadjusted for multiple comparisons**. Borderline findings, including Mid–Luxury and Luxury versus overall, should not be presented as familywise-confirmed discoveries. The `boot_p` columns are two-sided percentile-tail approximations; they were preserved for compatibility and are not the same construction as the null-recentred interaction p-value. A zero tail count among 2,000 draws is not a true probability of zero. Finite-replicate Monte Carlo uncertainty remains.

Product independence/exchangeability and representativeness are assumptions. The catalogue is not a probability sample; common brands/authors can induce dependence across products. Percentile coverage can be sensitive to skew and influential clusters, especially in smaller groups such as Lip Care (61 products). BCa/studentized alternatives and multiplicity-adjusted inference were not introduced because that would alter the submitted analytical decisions. No equivalence, causal, universal no-interaction, or assumption-free/design-based sampling claim is justified.

There are no unresolved numerical implementation discrepancies. **The preserved Word/HTML exports still require a final manuscript/export refresh before submission**; their original mistakes are intentionally documented rather than silently presenting those snapshots as corrected. Use the current notebook, corrected Markdown notes and `results/part_d/` as the canonical analysis.

Evidence: `results/part_d/verification.json`, `original_result_comparison.csv`, `diagnostics.json`, `weighting_sensitivity.csv`, and `results/execution_d.json`. Large data, logs and executed notebooks remain excluded from Git. Original author/AI provenance is preserved; corrected notes separately acknowledge this audit.

## Follow-up: Part A rerun from all six original CSVs

**Outcome: no significant issues or observed data errors found. All 1,093,970 rows and 46 columns match the existing merged dataset exactly**, including row/column order, missingness and pandas dtypes. The corrected notebook completed all assertions, and 49 additional independent checks passed.

The user supplied the six CSVs in local `archive/`. `preservation/part_a_rerun_before.json` records their sizes and SHA-256 hashes, the existing merged/processed fingerprints, and B/C/E/F source hashes. `preservation/part_a_rerun_before.zip` preserves A's notebook and supporting configuration/documentation. The A notebook itself was unchanged during this verification. Only explicit raw-directory selection (`SEPHORA_RAW_DIR`), the verification script, documentation and dataset exclusions were added.

`scripts/compare_part_a.py --raw-dir archive` ran A into the fresh ignored directory `data/part_a_reruns/20261123T215602+0800/data/processed/`. Compact reports are separate under `results/part_a_validation/`. Existing run/report directories are rejected. Before/after hashes confirm all six raw CSVs, the existing merged file, authoritative processed file, and B/C/E/F sources are unchanged. Previous result files were not regenerated.

| Check | Verified result |
| --- | --- |
| Catalogue | 8,494 rows; product keys unique and nonmissing |
| Review files | 602,130 + 206,725 + 116,262 + 119,317 + 49,977 = 1,094,411 rows; consistent schemas |
| Deduplication before imputation | 749 rows belong to duplicate groups; keep-first removes 441 rows, leaving 1,093,970 |
| IDs | Every retained author/product ID matches normalized lexical CSV input and the reference; none missing; 503,216 authors and 2,351 reviewed products |
| Join | All 1,093,970 reviews matched; zero unmatched; every one of the 26 joined product fields independently matches its catalogue source |
| Catalogue coverage | 6,143 catalogue products have no reviews in these files, as allowed by a review-left join; its `right_only = 0` does not imply all catalogue products have reviews |
| Conversion | Zero invalid/fractional-value issue records; valid review dates |
| All column values | Zero differing cells, including complete review text, outcomes, feedback, IDs, demographics and product metadata, compared in source-file/row order |
| Repeated author/product pairs | 4,660 pairs retained by design rather than automatically treated as duplicates |

The independent verifier reread the CSVs, separately implemented the declared normalization rules, recomputed duplicate removal, and checked every retained review field. It recomputed each author's case-insensitive distinct demographic values and first observed donor, checked every expected fill, verified observed values were never overwritten, and verified conflicting authors' missing values stayed missing. Product checks mapped each output product ID directly to an independently normalized catalogue, rather than relying only on the `matched` flag.

| Attribute | Missing before | Filled | Missing after | Missing rows left unfilled for conflicting authors |
| --- | ---: | ---: | ---: | ---: |
| Skin tone | 170,379 | 48,583 | 121,796 | 5,764 |
| Eye colour | 209,458 | 44,610 | 164,848 | 1,129 |
| Skin type | 111,403 | 33,773 | 77,630 | 3,366 |
| Hair colour | 226,597 | 55,376 | 171,221 | 4,684 |

Differences and classification:

- **Code corrections, with no data effect here.** String-ID ingestion prevents future numeric inference/rounding or loss of leading zeros. Every retained ID and fill matches the reference; there were no leading-zero author IDs. Schema validation, configurable paths and saved audits improve reproducibility without changing these data. No ID corruption was observed in the reference file.
- **Harmless footer metadata.** The reference is 219,310,137 bytes, SHA-256 `8bb2f5ace440e2b3fbeddf4950222e61a36a67624e3d80926b4e1fab21083e2e`; the rebuilt file is 219,310,081 bytes, SHA-256 `a2a97b7612433f4bbf8bc630b73da10f3dd2e7b4ba9e300af5bdf3692bc2c867`. Every byte before the footer is identical and the physical Parquet schema matches. The 56-byte size difference is confined to pandas/Arrow footer metadata: pandas 3.1.1 versus 3.0.6 and 24 Arrow text fields represented as `string` versus `large_string`. Both files report PyArrow 26.0.1 and load into identical pandas dtypes. No reference-data replacement is warranted.
- **Expected duplicates after imputation.** Attribute filling makes two retained rows duplicate earlier reviews, exactly as in the reference. A deduplicates before filling; the previously verified B removes these two rows, then 121 near-identical same-day resubmissions. This is an understood pipeline-ordering effect, not a new discrepancy or an unhandled downstream duplicate error.

Evidence: `results/part_a_validation/comparison.json`, `column_comparison.csv`, `independent_imputation.csv`, `execution.json`, and nine compact audit CSVs in `part_a/`. Raw files, original/rebuilt Parquet, logs and executed notebooks are excluded from Git. The raw `archive/` directory and original CSV filename patterns are explicitly ignored.

Together with the B follow-up, this verifies the separate raw → merged and merged → processed stages against the existing datasets. The retrospective preprocessing, snapshot timing and observational interpretation limits below still apply.

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

This B check establishes merged-to-processed reproducibility. At that stage the raw CSVs were unavailable; the later A follow-up above verifies the preceding integration stage. Neither check resolves the observational/prospective limitations below.

## A: integration and audit — initial static review

The left join uses `validate="many_to_one"`, rejects missing/duplicate product keys, retains unmatched reviews with an audit flag, and asserts the join preserves the number of review rows. Duplicate handling excludes feedback counts and file provenance; consistent-author imputation is restricted to authors with exactly one observed attribute value. These are coherent retrospective integration rules.

Corrections made:

- Input IDs are read as strings at CSV ingestion to prevent numeric inference from changing reviewer IDs before later conversion to strings.
- The raw directory is explicit and configurable; all six files must exist, and a schema mismatch between review files stops concatenation.
- Audit tables are now saved to `results/part_a/`; previously the heading promised saved reports but the code saved only Parquet.
- Shared paths remove dependence on the notebook launch directory.

The initial review lacked raw files; the follow-up above now verifies the join, coercion audit, fills, deduplication and row counts using the supplied CSVs. Case-insensitive author comparisons preserve the first original spelling; current B mappings expect the source spelling. Future new raw exports may require explicit normalization. The post-imputation duplicate pass in B is retained because filling attributes can make rows identical. A's left join cannot count catalogue products without reviews through the `right_only` indicator; a separate anti-join would be needed for that different question.

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
