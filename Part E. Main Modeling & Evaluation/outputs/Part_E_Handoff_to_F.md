# Part E to Part F handoff

Part F reruns the Part E pipeline with (1) the recommendation flag as the outcome and (2) log price instead of price segment. Keep everything else identical so the results are directly comparable.

## What to reuse from `03_main_model_E.ipynb`

Run Sections 1–3 unchanged (setup, loading, the `price`, `skin`, `cat`, `HL` and `cluster` columns, `REF`, `hl_terms`, `F_MAIN`). Then reuse:

- `fit_logit(formula, data)`: logistic regression with product-clustered standard errors.
- `or_table(res)`: coefficients, clustered SEs, odds ratios, 95% CIs and p-values.
- The joint Wald test code in Section 5.
- The evaluation code in Section 7: the same `GroupShuffleSplit`, `SEED = 5106`, and the two thresholds (0.5 and the training outcome rate).

## 1. Secondary outcome: recommendation

```python
rec = df[df["recommended"].notna()].copy()
rec["recommended"] = rec["recommended"].astype(int)
rec["cluster"] = rec["product_id"].astype("category").cat.codes  # recompute after filtering

F_REC = F_MAIN.replace("five_star ~", "recommended ~")
res_rec = fit_logit(F_REC, rec)
or_rec = or_table(res_rec)
```

- `recommended` is missing for 15.3% of reviews, leaving 926,031 reviews. State this in the report.
- The recommendation rate is 84.0%, so the second threshold is the training recommendation rate, alongside 0.5.
- For a like-for-like comparison, also refit `F_MAIN` on the same `rec` rows, so differences are not caused by the smaller sample.
- Recommendation and five-star rating measure different things. Report differences between them as findings, not as failures of robustness.

## 2. Sensitivity: log price instead of price segment

```python
F_LOGP = f"five_star ~ log_price * {REF[1]} + {REF[2]} + {hl_terms}"
res_logp = fit_logit(F_LOGP, df)
or_logp = or_table(res_logp)
```

- Keep the interaction with skin type so the specification mirrors the main model. It now has 4 terms, so its joint Wald test has 4 degrees of freedom.
- Do not include `price_segment` and `log_price` in the same model.
- The `log_price` odds ratio is per one-unit increase in log price (about a 2.7-fold price increase). Report `exp(coef × log(2))` for the change per doubling of price.

## Part E reference numbers to compare against

- Five-star main model, joint interaction test: χ²(12) = 11.33, p = 0.5005.
- Main model held-out ROC-AUC: 0.524.

## Do not add

- New predictors, other model types or a different split. Part F changes only the outcome or the price variable.
