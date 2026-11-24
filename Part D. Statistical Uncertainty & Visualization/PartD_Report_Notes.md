# Part D statistical uncertainty and group comparisons

Corrected notes from the 2026-11-24 audit. The original submission, attribution and AI-use log are preserved in `preservation/part_d_original_submission.zip`. Current results are under `results/part_d/`. Supplied HTML/Word exports are historical snapshots containing original errors, not updated submission versions.

## Method and estimand

The analysis uses 1,093,847 reviews from 2,351 products. Each of 2,000 replicates samples 2,351 products uniformly with replacement, retaining every review and the full multiplicity of repeated product draws. A group rate is total five-star reviews divided by total reviews in the replicate. The estimand remains review weighted, consistent with C; it is not an equal-product average.

All groups and contrasts share the same draws (seed 5106). Differences are computed within each replicate. The 95% intervals use the 2.5th and 97.5th percentiles with linear interpolation. Intervals are pointwise/nominal. The submitted choices of weighting, percentile method, contrasts and interaction test are unchanged.

This is a nonparametric product-cluster bootstrap, not assumption-free or probability-survey design-based inference. It assumes products are suitable independent/exchangeable clusters for the target population. Shared authors or brands may create additional dependence.

## Verified findings and corrections

- Overall five-star rate: **63.8600%**, 95% CI **63.0818–64.6181%**. Bootstrap SE: 0.3981 percentage points; naive SE: 0.04593 pp. Their SE ratio is 8.6675 and variance ratio is 75.1251. The 14,560-review variance equivalent applies to this estimator, not universally.
- Corrected unequal-cluster ICC: **0.049041** (original 0.049374). Between-product sums of squares use the review-weighted grand mean. Binary within-product sums of squares are `n × p × (1-p)`. This diagnostic does not enter the bootstrap.
- Review-weighted overall rate: **63.8600%**, versus **63.1063%** with equal product weights. The original 63.2447% labelled “All reviews” incorrectly averaged four segment rates. Luxury is lowest by reviews (60.9449%) but second-highest by products (64.10%), below Premium (64.99%). The original claim that Luxury is highest by products was incorrect; weighting still changes the question.
- For six price pairs, naive tests flag five and pointwise bootstrap intervals exclude zero for one, Mid minus Luxury. Thus **four**, not five, pairs lose nominal significance. Its `boot_p = 0.037` is a percentile-tail approximation and is not multiplicity adjusted. Luxury minus overall is −2.9151 pp, CI −5.8408 to −0.1422; its marginal exclusion should not be overstated.
- Overlapping skin-type group intervals do not establish equality. **Oily minus overall is −0.9607 pp**, CI **−1.3394 to −0.5976**; Not reported minus overall is +2.3012 pp, CI +1.0577 to +3.4251. Paired contrasts can be precise despite overlapping marginal intervals. A stored `boot_p = 0` means no simulated opposite-sign draws among 2,000, not a population probability of zero.
- **Five of nine**, not six of nine, category-versus-overall intervals exclude zero: Cleansers, Eye Care, Masks, Sunscreen, and Tools/Wellness/Self-Tan. Eye Care is −7.1643 pp, CI −9.4368 to −4.9251. Lip Care's contrast interval includes zero despite its highest point estimate; only 61 products contribute. These are unadjusted, not simultaneous, comparisons.
- The retained interaction test compares Luxury-minus-Budget risk differences for **Normal, Combination, Dry and Oily**. The observed range is 1.5992 pp; the recentred-bootstrap test with a plus-one correction gives **p = 0.194403**, Monte Carlo SE about **0.00885**. Equality of four gradients imposes three restrictions, not one. Not reported is plotted but excluded from this test by the original decision.

See the seven original-format CSVs in `results/part_d/` for every group and full precision. All seven reproduce before and after the technical corrections.

## Consistency with C E and F

C's counts and rates agree for every group and all 20 skin × price cells. D's raw cell rates and E's predictions standardized over a common covariate mix are different quantities. The comparison matches E's saved predictions, but both use the same reviews. Interval overlap is descriptive, not independent model validation or an equivalence test.

E includes **all five** skin levels and jointly tests 12 adjusted log-odds interactions (Wald p = **0.500491**). D tests one unadjusted price contrast across four types on the risk-difference scale. Neither rejects its own null at 5%, but they do not test the same hypothesis or establish absence of all interactions. E's Not reported odds ratio is conditional on Budget price, not an overall marginal risk difference.

E and F agree on the full-sample five-star model reference statistics. F's recommendation model has a different outcome and 926,031 eligible reviews, so it is not a direct numerical benchmark for D's all-review five-star rates. E/F were not refitted or changed.

## Remaining limitations

The submitted 2,000-replicate percentile method is retained. Tail endpoints and borderline exclusions have Monte Carlo uncertainty. BCa/studentized alternatives and simultaneous or multiplicity-adjusted intervals were not evaluated; there is no basis to promise their differences would be small. Total cluster count does not remove small-group or influential-product concerns.

Product representativeness and independence are assumptions. The supplied data include 16,115 reviews for one product, contradicting a universal 200-review cap; capture completeness remains unknown. Retrospective author filling and historical product snapshots retain the project's existing limitations. Observational comparisons do not establish causality, equivalence, or no relationship.

## Figures and preservation

The current D1–D5 figures are in `results/part_d/figures/`. D2 now displays the full Oily/Luxury lower bound. D3 uses a horizontal difference connector. D5 labels observed rates and adjusted predictions without an equivalence claim. These fixes do not change estimates or intervals.

The original author acknowledged Claude assistance with code, plots and initial prose. That statement is preserved in the original archive. Codex assisted this audit, independent verification, technical corrections and documentation; both contributions should remain in the team's final AI-use acknowledgement.
