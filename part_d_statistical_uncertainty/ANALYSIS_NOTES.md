# Statistical uncertainty and group comparisons

## Method

The estimand is the review-weighted five-star rate. Each of 2,000 replicates (seed 5106) samples 2,351 products uniformly with replacement and retains all reviews, including full multiplicity of repeated product draws. Rates are ratios of total five-star reviews to total reviews. A single draw matrix is used for all groups and paired contrasts. Intervals are the 2.5th and 97.5th percentiles with linear interpolation.

This nonparametric cluster bootstrap assumes suitable independent/exchangeable products. It is not assumption-free or probability-survey inference. All intervals and contrast flags are pointwise and unadjusted for multiple comparisons. `boot_p` fields are percentile-tail approximations, distinct from the null-centred interaction test.

## Results

- Overall rate: **63.8600%, 95% CI 63.0818–64.6181%**. Bootstrap SE is 0.3981 percentage points versus naive independent-review SE 0.04593 pp. The SE ratio is 8.6675 and variance ratio 75.1251. The 14,560-review variance equivalent is specific to this estimator, not a universal sample size. The unequal-cluster ANOVA ICC is 0.049041.
- Equal-product weighting gives 63.1063% overall. Under review weighting, Luxury is lowest (60.9449%). Under equal-product weighting, Premium is highest (64.9865%) and Luxury second (64.0999%). Weighting changes the estimand and price ordering.
- Five of six naive pairwise price tests are nominally significant; one product-bootstrap interval excludes zero (Mid minus Luxury). Four pairs lose nominal significance. Mid–Luxury has a percentile-tail approximation of 0.037. Luxury minus overall is −2.9151 pp, CI −5.8408 to −0.1422; its marginal exclusion should not be overstated.
- Oily minus overall is **−0.9607 pp**, CI **−1.3394 to −0.5976**. Not reported minus overall is **+2.3012 pp**, CI **+1.0577 to +3.4251**. Paired differences can be precise despite overlapping marginal group intervals. A stored tail approximation of zero means no simulated opposite-sign draws, not a population probability of zero.
- **Five of nine** category-versus-overall intervals exclude zero: Cleansers, Eye Care, Masks, Sunscreen, and Tools/Wellness/Self-Tan. Eye Care is −7.1643 pp, CI −9.4368 to −4.9251. Lip Care has the highest point estimate, but its contrast CI includes zero and only 61 products contribute.

## Interaction and comparison with E

D's specified test compares Luxury-minus-Budget risk differences for **Normal, Combination, Dry and Oily**. The observed range is 1.5992 pp. The null-centred bootstrap range test, with plus-one correction, gives **p = 0.194403** (Monte Carlo SE about 0.00885). Equality of four gradients imposes three restrictions. Not reported is displayed but excluded from this test.

E instead includes all five skin types and tests 12 adjusted log-odds interactions, with Wald **p = 0.500491**. Neither test rejects its own null at 5%, but they address different hypotheses and do not establish absence of all interactions. D's raw cell rates and E's standardized predictions use the same reviews and different covariate mixtures; their comparison is descriptive, not independent validation or equivalence testing. E's Not reported odds ratio is conditional on Budget price, not an overall marginal risk difference.

## Limits and outputs

Finite-replicate uncertainty remains for tail endpoints and borderline exclusions. BCa/studentized alternatives and multiplicity-adjusted inference were not evaluated. Total cluster count does not remove small-group or influential-product concerns. Product representativeness, cross-product dependence, historical snapshots and retrospective author filling limit generalization and prospective interpretations. The data include up to 16,115 reviews per product, so a universal 200-review cap is not supported. Observational comparisons do not establish causality or equivalence.

`outputs/` contains group rates, paired group differences, price pairs, 20 skin/price cells, five skin-specific gradients, the range test, observed-versus-adjusted predictions, and weighting sensitivity. `bootstrap_diagnostics.json` records settings and variance diagnostics. `outputs/figures/` contains the five uncertainty figures.
