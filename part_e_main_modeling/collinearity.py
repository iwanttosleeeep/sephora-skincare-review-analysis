"""Full-data VIFs for Part E's reduced (main-effects only) design."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from patsy import dmatrix
from statsmodels.stats.outliers_influence import variance_inflation_factor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from project_paths import output_dir, require_analysis

HIGHLIGHTS = ["hl_fragrance_free", "hl_clean", "hl_vegan", "hl_cruelty_free",
              "hl_hydrating", "hl_dullness", "hl_dryness", "hl_anti_aging",
              "highlights_missing"]


def main_effects_design(data):
    """Build the notebook's treatment coding without fitting/changing any model."""
    frame = data[["price_segment", "skin_type_cat", "category"] + HIGHLIGHTS].copy()
    frame["price"] = frame.price_segment.astype(str).map({
        "Budget (<$25)": "Budget", "Mid ($25-49)": "Mid",
        "Premium ($50-99)": "Premium", "Luxury ($100+)": "Luxury",
    })
    frame["skin"] = frame.skin_type_cat.astype(str)
    frame["cat"] = frame.category.astype(str)
    formula = ("C(price, Treatment('Budget')) + C(skin, Treatment('Normal'))"
               " + C(cat, Treatment('Moisturizers')) + " + " + ".join(HIGHLIGHTS))
    return dmatrix(formula, frame, return_type="dataframe", NA_action="raise")


def vif_table(design, names):
    """Keep the intercept for centred auxiliary regressions; report predictors only.

    Interaction terms are deliberately excluded: this diagnoses the reduced
    design, avoiding collinearity induced by product terms in the main model.
    """
    values = np.asarray(design, dtype=float)
    names = list(names)
    if values.ndim != 2 or values.shape[1] != len(names) or len(set(names)) != len(names):
        raise ValueError("Design columns and unique term names must align.")
    if names.count("Intercept") != 1 or any(":" in name for name in names):
        raise ValueError("Expected a main-effects design with an intercept and no interactions.")
    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("Design must be nonempty and finite.")
    if not np.all(values[:, names.index("Intercept")] == 1):
        raise ValueError("Intercept must be a column of ones.")
    rows = [{"model_term": name, "vif": variance_inflation_factor(values, i),
             "n_reviews": len(values)}
            for i, name in enumerate(names) if name != "Intercept"]
    result = pd.DataFrame(rows)
    if not np.isfinite(result.vif).all():
        raise ValueError("Nonfinite VIFs: investigate the design for exact collinearity.")
    return result


def main():
    data = pd.read_parquet(require_analysis(), columns=[
        "price_segment", "skin_type_cat", "category"] + HIGHLIGHTS)
    design = main_effects_design(data)
    result = vif_table(design, design.columns)
    destination = output_dir("E") / "vif_main_effects.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination, index=False)
    print(result.to_string(index=False))
    print(f"\nFull dataset; maximum VIF: {result.vif.max():.6f}; saved {destination}")


if __name__ == "__main__":
    main()
