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
import statsmodels.formula.api as smf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (roc_auc_score, f1_score, balanced_accuracy_score,
                             accuracy_score)

SEED = 5106
BASE_DIR = ROOT
DATA_PATH = require_analysis()
OUT_DIR = RESULTS_DIR / "part_f"
OUT_DIR.mkdir(parents=True, exist_ok=True)


df = pd.read_parquet(DATA_PATH)
PRICE_MAP = {"Budget (<$25)": "Budget", "Mid ($25-49)": "Mid", "Premium ($50-99)": "Premium", "Luxury ($100+)": "Luxury"}
df["price"] = df["price_segment"].astype(str).map(PRICE_MAP)
df["skin"] = df["skin_type_cat"].astype(str)
df["cat"] = df["category"].astype(str)
HL = ["hl_fragrance_free", "hl_clean", "hl_vegan", "hl_cruelty_free",
      "hl_hydrating", "hl_dullness", "hl_dryness", "hl_anti_aging", "highlights_missing"]
df["cluster"] = df["product_id"].astype("category").cat.codes

REF = ("C(price, Treatment('Budget'))", "C(skin, Treatment('Normal'))", "C(cat, Treatment('Moisturizers'))")
F_MAIN = f"five_star ~ {REF[0]} * {REF[1]} + {REF[2]} + {' + '.join(HL)}"
F_LOGP = f"five_star ~ log_price * {REF[1]} + {REF[2]} + {' + '.join(HL)}"

def fit_logit(formula, data):
    result = smf.logit(formula, data=data, missing="raise").fit(
        disp=False, maxiter=100, cov_type="cluster",
        cov_kwds={"groups": data["cluster"].to_numpy()})
    if not result.mle_retvals["converged"]:
        raise RuntimeError("Logistic model did not converge")
    return result

def joint_wald(res):
    names = list(res.params.index)
    inter_idx = [i for i, n in enumerate(names) if ":" in n]
    R = np.zeros((len(inter_idx), len(names)))
    for row, i in enumerate(inter_idx):
        R[row, i] = 1
    wald = res.wald_test(R, scalar=True)
    return float(wald.statistic), len(inter_idx), float(wald.pvalue)

def stars(p):
    return "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else ""

def evaluate(formula, data, outcome):
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    train_idx, test_idx = next(gss.split(data, groups=data["product_id"]))
    train, test = data.iloc[train_idx].copy(), data.iloc[test_idx].copy()
    assert set(train["product_id"]).isdisjoint(set(test["product_id"]))
    m = fit_logit(formula, train)
    y_test = test[outcome].to_numpy()
    prob = m.predict(test).to_numpy()
    thr = train[outcome].mean()          # training outcome rate threshold
    lbl = (prob >= thr).astype(int)
    return {"ROC-AUC": roc_auc_score(y_test, prob),
            "Balanced acc.": balanced_accuracy_score(y_test, lbl),
            "Macro F1": f1_score(y_test, lbl, average="macro"),
            "Accuracy": accuracy_score(y_test, lbl)}


rec = df[df["recommended"].notna()].copy()
rec["recommended"] = rec["recommended"].astype(int)
rec["cluster"] = rec["product_id"].astype("category").cat.codes

res_main_full = fit_logit(F_MAIN, df)                                  # Part E main model
res_main_rec  = fit_logit(F_MAIN, rec)                                 # five-star, rec sample
res_rec       = fit_logit(F_MAIN.replace("five_star ~", "recommended ~"), rec)  # recommendation
res_logp      = fit_logit(F_LOGP, df)                                  # log-price sensitivity
print("All four models converged:",
      all(r.mle_retvals["converged"] for r in [res_main_full, res_main_rec, res_rec, res_logp]))


PRICE_TERMS = [("Mid ($25-49)",     "C(price, Treatment('Budget'))[T.Mid]"),
               ("Premium ($50-99)", "C(price, Treatment('Budget'))[T.Premium]"),
               ("Luxury ($100+)",   "C(price, Treatment('Budget'))[T.Luxury]")]

def or_cell(res, term):
    ci = res.conf_int().loc[term]
    return f"{np.exp(res.params[term]):.3f} ({np.exp(ci[0]):.3f}\u2013{np.exp(ci[1]):.3f}){stars(res.pvalues[term])}"

table1 = pd.DataFrame({
    "Price segment": [t[0] for t in PRICE_TERMS],
    "Five-star, full sample (E)": [or_cell(res_main_full, t[1]) for t in PRICE_TERMS],
    "Five-star, rec sample":      [or_cell(res_main_rec,  t[1]) for t in PRICE_TERMS],
    "Recommendation, rec sample": [or_cell(res_rec,       t[1]) for t in PRICE_TERMS],
})
table1.to_csv(OUT_DIR / "table1_price_or_across_specifications.csv", index=False)
print("\nTable 1. Odds ratios for price segments (ref: Budget)")
print(table1.to_string(index=False))

w = [("Main model (Part E)", "Five-star, full sample", *joint_wald(res_main_full)),
     ("Main model, refit", "Five-star, rec sample", *joint_wald(res_main_rec)),
     ("Secondary outcome model", "Recommendation, rec sample", *joint_wald(res_rec)),
     ("Sensitivity model (log price)", "Five-star, full sample", *joint_wald(res_logp))]
table2 = pd.DataFrame(w, columns=["Model", "Outcome / sample", "chi2", "df", "p"])
table2["chi2 (df)"] = table2["chi2"].round(2).astype(str) + " (" + table2["df"].astype(str) + ")"
table2 = table2[["Model", "Outcome / sample", "chi2 (df)", "p"]].round({"p": 4})
table2.to_csv(OUT_DIR / "table2_wald_tests.csv", index=False)
print("\nTable 2. Joint Wald tests of the price x skin interaction")
print(table2.to_string(index=False))

b = res_logp.params["log_price"]; ci = res_logp.conf_int().loc["log_price"]; p = res_logp.pvalues["log_price"]
table3 = pd.DataFrame({
    "Scale": ["Normal skin: per 1-unit log price (~2.7x price)", "Normal skin: per doubling of price"],
    "Odds ratio": [np.exp(b), np.exp(b * np.log(2))],
    "95% CI": [f"{np.exp(ci[0]):.3f}\u2013{np.exp(ci[1]):.3f}",
               f"{np.exp(ci[0]*np.log(2)):.3f}\u2013{np.exp(ci[1]*np.log(2)):.3f}"],
    "p": [p, p],
}).round({"Odds ratio": 3, "p": 4})
table3.to_csv(OUT_DIR / "table3_log_price_sensitivity.csv", index=False)
print("\nTable 3. Sensitivity check: log price instead of price segments")
print(table3.to_string(index=False))


ev_main = evaluate(F_MAIN, df, "five_star")      # reproduces Part E evaluation
ev_rec  = evaluate(F_MAIN.replace("five_star ~", "recommended ~"), rec, "recommended")
ev_logp = evaluate(F_LOGP, df, "five_star")
table4 = pd.DataFrame([
    {"Model": "Main model (Part E), five-star", **ev_main},
    {"Model": "Recommendation model", **ev_rec},
    {"Model": "Log-price model, five-star", **ev_logp},
]).round(3)
table4.to_csv(OUT_DIR / "table4_held_out_evaluation.csv", index=False)
print("\nTable 4. Held-out evaluation (threshold = training outcome rate)")
print(table4.to_string(index=False))
print(f"\nAll tables saved to {OUT_DIR}")

