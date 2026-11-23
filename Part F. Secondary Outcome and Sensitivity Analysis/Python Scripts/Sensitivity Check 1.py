# Find only this project (never search the user's home directory).
import sys
from pathlib import Path
_PROJECT_ROOT = next((p for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]
                      if (p / "project_paths.py").is_file()), None)
if _PROJECT_ROOT is None:
    raise FileNotFoundError("Open the notebook within the project folder.")
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from project_paths import ROOT, RESULTS_DIR, ANALYSIS_PATH, RAW_DIR, PROCESSED_DIR, require_analysis, require_merged


from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (roc_auc_score, f1_score, balanced_accuracy_score,
                             confusion_matrix, accuracy_score)

SEED = 5106
BASE_DIR = ROOT
DATA_PATH = require_analysis()
OUT_DIR = RESULTS_DIR / "part_f"
OUT_DIR.mkdir(parents=True, exist_ok=True)


PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 200, "font.size": 10,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
})


df = pd.read_parquet(DATA_PATH)
print("Rows:", f"{len(df):,}", "| Products:", df["product_id"].nunique(), "| Five-star rate:", round(df["five_star"].mean(), 4))


PRICE_MAP = {"Budget (<$25)": "Budget", "Mid ($25-49)": "Mid", "Premium ($50-99)": "Premium", "Luxury ($100+)": "Luxury"}
PRICE_ORDER = ["Budget", "Mid", "Premium", "Luxury"]
SKIN_ORDER = ["Normal", "Combination", "Dry", "Oily", "Not reported"]

df["price"] = df["price_segment"].astype(str).map(PRICE_MAP)
df["skin"] = df["skin_type_cat"].astype(str)
df["cat"] = df["category"].astype(str)
assert df["price"].notna().all() and set(df["skin"]) == set(SKIN_ORDER)

HL = ["hl_fragrance_free", "hl_clean", "hl_vegan", "hl_cruelty_free",
      "hl_hydrating", "hl_dullness", "hl_dryness", "hl_anti_aging", "highlights_missing"]


LEAKAGE = ["rating", "recommended", "review_text", "review_title", "helpfulness",
           "loves_count", "product_rating", "product_reviews"]
MAIN_TERMS = ["price", "skin", "cat"] + HL
assert not set(LEAKAGE) & set(MAIN_TERMS)


df["cluster"] = df["product_id"].astype("category").cat.codes


REF = ("C(price, Treatment('Budget'))", "C(skin, Treatment('Normal'))", "C(cat, Treatment('Moisturizers'))")
hl_terms = " + ".join(HL)
F_MAIN = f"five_star ~ {REF[0]} * {REF[1]} + {REF[2]} + {hl_terms}"

def fit_logit(formula, data):
    result = smf.logit(formula, data=data, missing="raise").fit(
        disp=False, maxiter=100, cov_type="cluster",
        cov_kwds={"groups": data["cluster"].to_numpy()})
    if not result.mle_retvals["converged"]:
        raise RuntimeError("Logistic model did not converge")
    return result

def tidy_label(term):
    t = term
    for long, short in [("C(price, Treatment('Budget'))[T.", "Price: "),
                        ("C(skin, Treatment('Normal'))[T.", "Skin: "),
                        ("C(cat, Treatment('Moisturizers'))[T.", "Category: ")]:
        t = t.replace(long, short)
    t = t.replace("]", "").replace(":Skin: ", " x Skin: ")
    t = t.replace("hl_", "Highlight: ").replace("highlights_missing", "No highlights listed")
    return t

def or_table(res):
    ci = res.conf_int()
    out = pd.DataFrame({
        "term": [tidy_label(t) for t in res.params.index],
        "model_term": res.params.index,
        "coef_log_odds": res.params.values,
        "se_clustered": res.bse.values,
        "z": res.tvalues.values,
        "odds_ratio": np.exp(res.params.values),
        "ci_low": np.exp(ci[0].values),
        "ci_high": np.exp(ci[1].values),
        "p_value": res.pvalues.values,
    })
    return out[out["term"] != "Intercept"].reset_index(drop=True)

def joint_wald(res, label):
    names = list(res.params.index)
    inter_idx = [i for i, n in enumerate(names) if ":" in n]
    R = np.zeros((len(inter_idx), len(names)))
    for row, i in enumerate(inter_idx):
        R[row, i] = 1
    wald = res.wald_test(R, scalar=True)
    chi2, df_w, p = float(wald.statistic), len(inter_idx), float(wald.pvalue)
    print(f"{label}: joint Wald test chi2({df_w}) = {chi2:.2f}, p = {p:.4f}")
    return {"model": label, "wald_chi2": chi2, "wald_df": df_w, "wald_p": p}

def evaluate(formula, data, outcome, model_name):

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    train_idx, test_idx = next(gss.split(data, groups=data["product_id"]))
    train, test = data.iloc[train_idx].copy(), data.iloc[test_idx].copy()
    assert set(train["product_id"]).isdisjoint(set(test["product_id"]))
    m = fit_logit(formula, train)
    y_test = test[outcome].to_numpy()
    prob = m.predict(test).to_numpy()
    train_rate = train[outcome].mean()
    thresholds = {"0.5 (default)": 0.5, f"{train_rate:.3f} (training outcome rate)": train_rate}
    print(f"{model_name} | Train: {len(train):,} reviews | Test: {len(test):,} reviews | "
          f"test outcome rate {y_test.mean():.3f}")
    rows = [{"model": model_name, "threshold": thr_name,
             "ROC-AUC": roc_auc_score(y_test, prob),
             "Balanced accuracy": balanced_accuracy_score(y_test, (prob >= thr).astype(int)),
             "Macro F1": f1_score(y_test, (prob >= thr).astype(int), average="macro"),
             "Accuracy": accuracy_score(y_test, (prob >= thr).astype(int)),
             "Share predicted positive": (prob >= thr).mean()}
            for thr_name, thr in thresholds.items()]
    return pd.DataFrame(rows)

F_LOGP = f"five_star ~ log_price * {REF[1]} + {REF[2]} + {hl_terms}"
res_logp = fit_logit(F_LOGP, df)
or_logp = or_table(res_logp)
or_logp.to_csv(OUT_DIR / "odds_ratios_log_price_model.csv", index=False)
print("log_price model converged:", res_logp.mle_retvals["converged"], "| parameters:", len(res_logp.params))


b = res_logp.params["log_price"]
ci = res_logp.conf_int().loc["log_price"]
per_unit = np.exp([b, ci[0], ci[1]])
per_double = np.exp([b * np.log(2), ci[0] * np.log(2), ci[1] * np.log(2)])
logp_row = pd.DataFrame({
    "scale": ["Normal skin: per 1-unit log price (~2.7x price)", "Normal skin: per doubling of price"],
    "odds_ratio": [per_unit[0], per_double[0]],
    "ci_low": [per_unit[1], per_double[1]],
    "ci_high": [per_unit[2], per_double[2]],
    "p_value": res_logp.pvalues["log_price"],
})
logp_row.to_csv(OUT_DIR / "log_price_odds_ratios.csv", index=False)
logp_row.round(4)


wald_logp = joint_wald(res_logp, "Log-price model (log_price x skin)")
pd.DataFrame([wald_logp]).to_csv(OUT_DIR / "wald_test_log_price_model.csv", index=False)


metrics_logp = evaluate(F_LOGP, df, "five_star", "Log-price model")
metrics_logp.to_csv(OUT_DIR / "evaluation_metrics_log_price.csv", index=False)
metrics_logp.round(3)