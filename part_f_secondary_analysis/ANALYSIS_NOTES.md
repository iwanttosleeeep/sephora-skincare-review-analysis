# Secondary outcome and sensitivity analysis

## Specifications and reference groups

All models are adjusted logistic regressions with product-clustered covariance. They retain E's category and highlight controls, with **Budget price, Normal skin and Moisturizers** as categorical reference groups. Eight highlight indicators and the missing-highlights indicator enter as controls. No rating-derived variable or 2023 snapshot flag is a predictor.

1. `recommendation_analysis.py` changes the outcome to `recommended`, dropping only rows with a missing recommendation (926,031 eligible reviews). It also refits the five-star interaction model on those exact rows for a like-for-like sample comparison.
2. `log_price_sensitivity.py` replaces price segments with natural log price, retaining log-price × skin interactions. It never includes both price representations together.
3. `model_comparison.py` presents the full-sample five-star model, same-sample five-star model, recommendation model and log-price sensitivity together.

**Every reported main price odds ratio is conditional on Normal skin.** In segment models it compares the named segment against Budget while holding the other model predictors fixed. Interaction terms are odds-ratio ratios modifying that reference-skin association; they are not stand-alone price effects for other skin types. The full odds-ratio CSVs include an `effect_context` field, and comparison price tables explicitly identify Normal skin and Budget.

In the log-price model, `exp(beta)` is the price odds ratio for a one-unit rise in natural log price (about a 2.718-fold price increase), conditional on Normal skin. `exp(beta × ln(2))` is the corresponding odds ratio per doubling. Its skin main effects refer to `log_price = 0` ($1), not Budget products. Category effects are relative to Moisturizers; highlight effects compare a claim indicator of one versus zero conditional on the remaining controls.

## Findings

The full-sample main-model joint interaction p-value is 0.5005. On the recommendation-eligible sample it is 0.1524 for the five-star outcome and 0.1610 for recommendation. For log-price × skin it is 0.0784 (four interaction terms). These are failures to reject their respective nulls, not evidence of equivalence or no association.

For Normal-skin reviewers, the log-price odds ratio per doubling is approximately 1.025 (95% CI 0.982–1.069), p = 0.2561. Table 1 gives the conditional segment-price odds ratios across the three outcome/sample specifications. The recommendation models describe a later eligible review sample and a different outcome; changes from five-star results should not be interpreted as a controlled model-superiority test.

Held-out product AUC is approximately 0.524 for E's main five-star model, 0.551 for recommendation and 0.518 for log-price/five-star. Each outcome uses its eligible product population. Evaluation uses the same 80/20 product split algorithm and seed 5106, with both 0.5 and training-outcome-rate thresholds; the summary table uses the training-rate threshold. No test outcomes determine a threshold.

## Relation to descriptive analyses

C and D report unadjusted review-weighted rates and risk differences. E/F report adjusted odds ratios and standardized predictions. D's range test compares only Luxury-minus-Budget risk differences across four reported skin types; E/F segment models test 12 adjusted log-odds interactions across all five skin levels. Their effect scales, contrasts and hypotheses differ.

Confidence intervals and significance annotations are nominal, without multiplicity adjustment. Product independence, global feature preparation, author filling across products and 2023 snapshots applied to historical reviews retain the limitations described in the root README. The results are observational and not causal. Recent-review and repeat-author exclusions are not additional fitted specifications in this final analysis.
