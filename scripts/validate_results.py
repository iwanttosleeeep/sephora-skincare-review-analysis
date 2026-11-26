"""Validate final dataset, cluster intervals, model results and interpretation metadata."""
import ast
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_paths import PART_D, RUN_DIR, output_dir, require_analysis

PRICE = ["Budget (<$25)", "Mid ($25-49)", "Premium ($50-99)", "Luxury ($100+)"]
SKIN = ["Normal", "Combination", "Dry", "Oily", "Not reported"]
CATEGORY = ["Moisturizers", "Treatments", "Cleansers", "Eye Care", "Masks", "Lip Care", "Sunscreen",
            "Minis & Sets", "Tools, Wellness & Self-Tan"]


def endpoints(values):
    """Explicit order-statistic interpolation, independently of np.percentile."""
    values = np.sort(values, axis=0)
    answer = []
    for q in [.025, .975]:
        position = (len(values) - 1) * q
        lower = int(position)
        fraction = position - lower
        answer.append(values[lower] * (1-fraction) + values[lower+1] * fraction)
    return np.asarray(answer)


def main():
    checks = []

    def check(name, condition, **detail):
        checks.append({"check": name, "passed": bool(condition), **detail})

    def close(name, actual, expected, atol=1e-10):
        actual, expected = np.asarray(actual), np.asarray(expected)
        check(name, actual.shape == expected.shape and np.allclose(actual, expected, atol=atol, rtol=1e-10),
              max_abs_difference=float(np.max(np.abs(actual-expected))))

    output = output_dir("D")
    tables = {p.stem: pd.read_csv(p) for p in output.glob("*.csv")}
    diag = json.loads((output / "bootstrap_diagnostics.json").read_text())
    df = pd.read_parquet(require_analysis())
    check("unique review IDs and complete grouping keys", df.review_id.is_unique and df[["product_id", "author_id", "price_segment", "skin_type_cat", "category"]].notna().all().all())
    predictors = ["price_segment", "skin_type_cat", "category", "highlights_missing"] + [c for c in df if c.startswith("hl_")]
    check("model predictors complete", df[predictors].notna().all().all())
    check("positive prices and exact log transform", (df.price_usd>0).all() and np.allclose(df.log_price,np.log(df.price_usd)))
    check("product predictors constant within product", df.groupby("product_id")[["price_usd", "category"]+[c for c in predictors if c.startswith("hl_") or c=="highlights_missing"]].nunique(dropna=False).le(1).all().all())
    distribution=pd.read_csv(output_dir("C")/"rating_distribution.csv").set_index("rating").loc[[1,2,3,4,5]]
    check("C rating distribution",np.array_equal(distribution.n_reviews,df.rating.value_counts().reindex([1,2,3,4,5])))
    reporting = df.skin_type_cat.eq("Not reported")
    yearly = pd.read_csv(output_dir("C") / "skin_type_not_reported_by_year.csv").set_index("review_year").sort_index()
    year_counts = pd.crosstab(df.review_year, reporting).reindex(columns=[False, True], fill_value=0)
    check("C skin reporting: yearly counts", np.array_equal(yearly.n_reviews, year_counts.sum(axis=1))
          and np.array_equal(yearly.n_not_reported, year_counts[True])
          and np.array_equal(yearly.n_reported, year_counts[False]))
    close("C skin reporting: yearly shares", yearly.not_reported_share_pct, 100*year_counts[True]/year_counts.sum(axis=1))
    recent = yearly.loc[yearly.index >= 2018]
    check("C skin reporting: expectation flags retain exceptions", np.array_equal(
        recent.matches_expected.astype(bool), recent.not_reported_share_pct.lt(2)))
    check("C skin reporting: 2023 under-2-percent expectation fails", not bool(yearly.loc[2023, "matches_expected"]))
    activity = pd.read_csv(output_dir("C") / "skin_type_author_activity.csv").set_index("skin_type_reporting").loc[["Not reported", "Reported"]]
    author_totals = df.author_id.value_counts(sort=False)
    for group, mask in [("Not reported", reporting), ("Reported", ~reporting)]:
        ids = df.loc[mask, "author_id"]
        row = activity.loc[group]
        close(f"C {group}: full-dataset author medians",
              [row.median_author_reviews_review_weighted, row.median_author_reviews_author_weighted],
              [ids.map(author_totals).median(), ids.drop_duplicates().map(author_totals).median()])
        check(f"C {group}: activity denominators", row.n_reviews == len(ids) and row.n_authors == ids.nunique())
    periods = pd.read_csv(output_dir("C") / "skin_type_five_star_by_period.csv").set_index(["period", "skin_type_reporting"])
    for period, year_mask in [("Before 2017", df.review_year.lt(2017)), ("2017 onward", df.review_year.ge(2017))]:
        for group, status_mask in [("Not reported", reporting), ("Reported", ~reporting)]:
            sample = df.loc[year_mask & status_mask]
            row = periods.loc[(period, group)]
            check(f"C {period}/{group}: reporting counts", row.n_reviews == len(sample)
                  and row.n_authors == sample.author_id.nunique() and row.n_five_star == sample.five_star.sum())
            close(f"C {period}/{group}: five-star rate", [row.five_star_rate_pct], [100*sample.five_star.mean()])
    check("C reporting period expectations at one decimal", periods.matches_expected_one_decimal.all())
    check("authoritative dataset shape/outcome", len(df) == 1_093_847 and (df.five_star == df.rating.eq(5)).all())
    products, product_code = np.unique(df.product_id.to_numpy(dtype=str), return_inverse=True)
    P, B = len(products), 2000
    idx = np.random.default_rng(5106).integers(0, P, size=(B, P), dtype=np.int32)
    check("draw matrix seed and shape", idx.shape == (2000, 2351)
          and hashlib.sha256(idx.tobytes()).hexdigest() == diag["draw_indices_sha256"])
    multiplicity = np.zeros((B, P), dtype=np.int32)
    np.add.at(multiplicity, (np.repeat(np.arange(B), P), idx.ravel()), 1)
    check("whole-product multiplicities preserved", (multiplicity.sum(axis=1) == P).all() and multiplicity.max() > 1)
    outcome = df.five_star.to_numpy(dtype=np.int64)
    group_results = {}
    minimum_denominator = None
    for key, levels in [("price_segment", PRICE), ("skin_type_cat", SKIN), ("category", CATEGORY),
                        ("cell", [f"{s} | {p}" for s in SKIN for p in PRICE])]:
        values = df[key] if key != "cell" else df.skin_type_cat.astype(str) + " | " + df.price_segment.astype(str)
        codes = pd.Categorical(values, categories=levels).codes.astype(np.int64)
        check(f"{key} has no missing/unmapped values", (codes >= 0).all())
        code = product_code * len(levels) + codes
        counts = np.bincount(code, minlength=P*len(levels)).reshape(P, len(levels))
        successes = np.bincount(code, weights=outcome, minlength=P*len(levels)).reshape(P, len(levels))
        denominators = multiplicity @ counts
        boot = (multiplicity @ successes) / denominators
        minimum_denominator = int(denominators.min()) if minimum_denominator is None else min(minimum_denominator, int(denominators.min()))
        check(f"{key}: all 2000 bootstrap denominators positive", (denominators > 0).all() and np.isfinite(boot).all())
        points = successes.sum(0) / counts.sum(0)
        unique_products = (counts > 0).sum(0)
        group_results[key] = {"boot": boot, "points": points, "n": counts.sum(0), "products": unique_products}
    overall_n = np.bincount(product_code)
    overall_y = np.bincount(product_code, weights=outcome)
    overall_boot = (multiplicity @ overall_y) / (multiplicity @ overall_n)
    overall_point = outcome.mean()
    rates = tables["ci_group_rates"]
    overall_row = rates[rates.group_var.eq("overall")].iloc[0]
    close("overall point and percentile endpoints", overall_row[["five_star_rate_pct", "ci_low_pct", "ci_high_pct"]].to_numpy(float),
          np.r_[100*overall_point, 100*endpoints(overall_boot)])
    for key, label, levels, cfile in [("price_segment", "price_segment", PRICE, "by_price_segment.csv"),
                                     ("skin_type_cat", "skin_type", SKIN, "by_skin_type.csv"),
                                     ("category", "category", CATEGORY, "by_category.csv")]:
        group = group_results[key]
        actual = rates[rates.group_var.eq(label)].set_index("group").loc[levels]
        close(f"{key}: points", actual.five_star_rate_pct, 100*group["points"])
        close(f"{key}: percentile CIs", actual[["ci_low_pct", "ci_high_pct"]].to_numpy().T, 100*endpoints(group["boot"]))
        standard_error = np.sqrt(((group["boot"] - group["boot"].mean(0))**2).sum(0)/(B-1))
        close(f"{key}: bootstrap SE ddof=1", actual.boot_se_pp, 100*standard_error)
        check(f"{key}: review and product counts", np.array_equal(actual.n_reviews, group["n"]) and np.array_equal(actual.n_products, group["products"]))
        naive = np.sqrt(group["points"]*(1-group["points"])/group["n"])
        close(f"{key}: naive SE", actual.naive_se_pp, 100*naive)
        wilson = np.array([[ci.low, ci.high] for ci in [
            binomtest(int(round(p*n)), int(n)).proportion_ci(confidence_level=.95, method="wilson")
            for p, n in zip(group["points"], group["n"])]])
        close(f"{key}: independent SciPy Wilson intervals", actual[["naive_ci_low_pct", "naive_ci_high_pct"]], 100*wilson)
        close(f"{key}: variance/design effect", actual.design_effect, (standard_error/naive)**2)
        c = pd.read_csv(output_dir("C") / cfile).set_index(key).loc[levels]
        close(f"{key}: Part C rates", c.five_star_rate_pct, actual.five_star_rate_pct.round(2), atol=1e-12)
        check(f"{key}: Part C counts", np.array_equal(c.n_reviews, actual.n_reviews) and np.array_equal(c.n_products, actual.n_products))
        diffs = tables["ci_differences"]
        actual_diff = diffs[diffs.group_var.eq(label)].set_index("group").loc[levels]
        paired = 100*(group["boot"] - overall_boot[:, None])
        close(f"{key}: paired difference CIs", actual_diff[["diff_ci_low_pp", "diff_ci_high_pp"]].to_numpy().T, endpoints(paired))
        close(f"{key}: tail-area approximation", actual_diff.boot_p,
              np.minimum(2*np.minimum((paired<=0).mean(0), (paired>=0).mean(0)), 1.))
        interval = endpoints(paired)
        check(f"{key}: nominal difference flags", np.array_equal(actual_diff.ci_excludes_zero,
                                                                 (interval[0]>0)|(interval[1]<0)))
    cell = group_results["cell"]
    cells = tables["ci_skin_x_price_cells"]
    close("all 20 cell rates", cells.five_star_rate_pct, 100*cell["points"])
    close("all 20 cell CIs", cells[["ci_low_pct", "ci_high_pct"]].to_numpy().T, 100*endpoints(cell["boot"]))
    check("all 20 cell counts", np.array_equal(cells.n_reviews, cell["n"]) and np.array_equal(cells.n_products, cell["products"]))
    c_cross = pd.read_csv(output_dir("C") / "by_price_skin_type.csv").set_index(["skin_type_cat", "price_segment"])
    c_cross = c_cross.loc[pd.MultiIndex.from_product([SKIN, PRICE])]
    close("Part C cross-cell rates", c_cross.five_star_rate_pct, cells.five_star_rate_pct.round(2))
    pairwise = tables["ci_pairwise_price"]
    k = 0
    for i in range(4):
        for j in range(i+1, 4):
            delta = 100*(group_results["price_segment"]["boot"][:,i] - group_results["price_segment"]["boot"][:,j])
            row = pairwise.iloc[k]
            close(f"pairwise {i}-{j}: paired CI", row[["boot_ci_low_pp", "boot_ci_high_pp"]].to_numpy(float), endpoints(delta))
            check(f"pairwise {i}-{j}: pointwise flag", bool(row.boot_significant_5pct) == bool((endpoints(delta)[0]>0)|(endpoints(delta)[1]<0)))
            ps = group_results["price_segment"]["points"]
            ns = group_results["price_segment"]["n"]
            pooled = (ps[i]*ns[i]+ps[j]*ns[j])/(ns[i]+ns[j])
            z = (ps[i]-ps[j])/np.sqrt(pooled*(1-pooled)*(1/ns[i]+1/ns[j]))
            close(f"pairwise {i}-{j}: naive normal reference", [row.naive_z,row.naive_p], [z,2*norm.sf(abs(z))])
            close(f"pairwise {i}-{j}: tail approximation", [row.boot_p], [min(2*min((delta<=0).mean(),(delta>=0).mean()),1)])
            k += 1
    gradient_boot = 100*(cell["boot"][:,3::4] - cell["boot"][:,0::4])
    gradient_point = 100*(cell["points"][3::4] - cell["points"][0::4])
    grad = tables["ci_price_gradient_by_skin"]
    close("all five gradient points", grad.gradient_luxury_minus_budget_pp, gradient_point)
    close("all five paired gradient CIs", grad[["ci_low_pp", "ci_high_pp"]].to_numpy().T, endpoints(gradient_boot))
    check("category contrast count is five of nine", tables['ci_differences'].query("group_var == 'category'").ci_excludes_zero.sum()==5)
    oily=tables['ci_differences'].query("group_var == 'skin_type' and group == 'Oily'").iloc[0]
    check("Oily paired contrast excludes zero", bool(oily.ci_excludes_zero) and oily.diff_ci_high_pp<0)
    errors = gradient_boot[:,:4] - gradient_point[:4]
    null_ranges = errors.max(1) - errors.min(1)
    observed_range = np.ptp(gradient_point[:4])
    p_int = (1 + (null_ranges >= observed_range).sum())/(B+1)
    inter = tables["interaction_test"].iloc[0]
    close("null-centred four-skin range test and plus-one p", [inter.statistic_range_pp, inter.p_value], [observed_range, p_int])
    # Verify the corrected ICC by expanding residuals at the review level.
    means = overall_y / overall_n
    ssb = ((means[product_code] - overall_point)**2).sum()
    ssw = ((outcome - means[product_code])**2).sum()
    msb, msw = ssb/(P-1), ssw/(len(df)-P)
    n0 = (len(df) - (overall_n**2).sum()/len(df))/(P-1)
    icc = (msb-msw)/(msb+(n0-1)*msw)
    close("ICC: direct binary review-level sums of squares", [diag["ms_between"], diag["ms_within"], diag["icc"]], [msb, msw, icc])
    close("correct review and product weighted overall rates", [diag["review_weighted_overall_pct"], diag["product_weighted_overall_pct"]], [100*overall_point, 100*means.mean()])
    weighting=tables['weighting_sensitivity'].set_index('price_segment').loc[PRICE]
    product_means=df.groupby(['product_id','price_segment'],observed=True).five_star.mean().groupby(level='price_segment',observed=True).mean().reindex(PRICE)
    close("weighting sensitivity: all product-weighted rates",weighting.product_weighted_pct,100*product_means)
    check("Premium, not Luxury, is highest with equal product weights",weighting.product_weighted_pct.idxmax()==PRICE[2] and weighting.product_weighted_pct.rank().loc[PRICE[3]]==3)
    se_overall = overall_boot.std(ddof=1)
    naive_overall = np.sqrt(overall_point*(1-overall_point)/len(df))
    close("overall bootstrap SE and variance ratio", [overall_row.boot_se_pp, overall_row.design_effect], [100*se_overall,(se_overall/naive_overall)**2])
    wilson_all=binomtest(int(outcome.sum()),len(outcome)).proportion_ci(confidence_level=.95,method="wilson")
    close("overall independent SciPy Wilson interval", [overall_row.naive_ci_low_pct,overall_row.naive_ci_high_pct],100*np.array([wilson_all.low,wilson_all.high]))
    # Unequal-size toy clusters: expansion must preserve repeated cluster copies.
    book = json.loads((PART_D / "04_statistical_uncertainty.ipynb").read_text())
    engine = next(node for c in book["cells"] if c["cell_type"]=="code" for node in ast.parse("".join(c["source"])).body
                  if isinstance(node, ast.FunctionDef) and node.name=="boot_rates")
    toy_idx=np.array([[0,0,2],[1,2,2]],dtype=np.int32)
    namespace={"np":np,"IDX":toy_idx}
    exec(compile(ast.Module(body=[engine],type_ignores=[]),"bootstrap_engine_fixture","exec"),namespace)
    toy=pd.DataFrame({"product":[0,0,0,1,2,2],"group":[0,0,0,0,1,1],"y":[1,1,0,0,1,0]})
    tn=np.array([[3,0],[1,0],[0,2]],float);ty=np.array([[2,0],[0,0],[0,1]],float)
    expanded=np.array([pd.concat([toy[toy['product']==i] for i in draw]).groupby('group').y.mean().reindex([0,1]).to_numpy() for draw in toy_idx])
    close("engine equals literal expansion of unequal repeated products",namespace['boot_rates'](tn,ty),expanded)
    try:
        namespace['boot_rates'](tn,ty,np.array([[0,0,0]],np.int32))
        rejects_empty=False
    except ValueError:
        rejects_empty=True
    check("empty bootstrap groups fail explicitly",rejects_empty)
    # E/F checks compare their actual saved artifacts; no model refitting.
    model=pd.read_csv(ROOT/diag['part_e_predictions_path'])
    model['price_segment']=model.price.map(dict(zip(['Budget','Mid','Premium','Luxury'],PRICE)))
    model=model.set_index(['skin','price_segment']).loc[pd.MultiIndex.from_product([SKIN,PRICE])]
    compared=tables['observed_vs_model']
    close("D/E raw cell observations",compared.observed_pct,cells.five_star_rate_pct)
    close("D/E adjusted points and intervals",compared[['model_pred_pct','model_ci_low_pct','model_ci_high_pct']],100*model[['pred','low','high']])
    wald=pd.read_csv(output_dir("E")/"wald_interaction.csv").iloc[0]
    f_wald=pd.read_csv(output_dir("F")/"table2_wald_tests.csv").iloc[0]
    close("E/F main-model Wald reference",[round(float(wald.wald_p),4)],[float(f_wald['p'])])
    check("distinct interaction hypotheses recorded", int(wald.wald_df)==12 and inter.skin_types=='Normal, Combination, Dry, Oily')
    e_or=pd.read_csv(output_dir("E")/"odds_ratios_main_model.csv")
    check("E includes Not reported interactions", e_or.model_term.str.contains('Not reported',regex=False).sum()==4)
    vif = pd.read_csv(output_dir("E") / "vif_main_effects.csv")
    reduced_terms = pd.read_csv(output_dir("E") / "odds_ratios_reduced_model.csv").model_term.tolist()
    check("E VIF: exact reduced-model terms, no intercept/interactions",
          vif.model_term.tolist() == reduced_terms and vif.model_term.is_unique
          and not vif.model_term.eq("Intercept").any() and not vif.model_term.str.contains(":").any())
    check("E VIF: full analysis sample", vif.n_reviews.eq(len(df)).all())
    # Independent dummy construction and inverse centred correlation matrix.
    # diag(inv(corr(X))) equals auxiliary-OLS VIFs with an intercept.
    vif_columns, vif_names = [], []
    for column, levels, variable, reference in [
            ("price_segment", PRICE, "price", "Budget"),
            ("skin_type_cat", SKIN, "skin", "Normal"),
            ("category", CATEGORY, "cat", "Moisturizers")]:
        for level in sorted(levels[1:]):
            label = level.split(" (")[0] if variable == "price" else level
            vif_names.append(f"C({variable}, Treatment('{reference}'))[T.{label}]")
            vif_columns.append(df[column].eq(level).to_numpy())
    for column in ["hl_fragrance_free", "hl_clean", "hl_vegan", "hl_cruelty_free",
                   "hl_hydrating", "hl_dullness", "hl_dryness", "hl_anti_aging", "highlights_missing"]:
        vif_names.append(column)
        vif_columns.append(df[column].to_numpy())
    vif_design = np.column_stack(vif_columns).astype(float)
    independent_vif = np.diag(np.linalg.inv(np.corrcoef(vif_design, rowvar=False)))
    check("E VIF: Budget/Normal/Moisturizers reference coding", vif.model_term.tolist() == vif_names)
    close("E VIF: independent inverse-correlation calculation", vif.vif, independent_vif, atol=1e-8)
    check("E VIF: finite, at least one, below 2.5", np.isfinite(vif.vif).all()
          and vif.vif.ge(1-1e-10).all() and vif.vif.lt(2.5).all())
    del vif_columns, vif_design
    e_auc=pd.read_csv(output_dir("E")/"evaluation_metrics.csv").query("model == 'Main model'")['ROC-AUC'].iloc[0]
    f_auc=pd.read_csv(output_dir("F")/"table4_held_out_evaluation.csv").iloc[0]['ROC-AUC']
    close("E/F main five-star evaluation reference",[round(e_auc,3)],[f_auc])
    check("F recommendation eligibility remains a separate outcome",df.recommended.notna().sum()==926031)
    check("no universal 200-review cap",int(overall_n.max())==16115 and (overall_n>200).any())
    execution=json.loads((RUN_DIR/'execution.json').read_text())
    check("complete downstream execution on authoritative input", {s['part'] for s in execution['steps']}>=set('CDEF') and all(s['exit_code']==0 for s in execution['steps'])
          and execution['analysis_sha256']==hashlib.file_digest(require_analysis().open('rb'),'sha256').hexdigest())
    for part, names in {"E":["odds_ratios_main_model.csv","odds_ratios_reduced_model.csv"],
                        "F":["odds_ratios_log_price_model.csv","odds_ratios_main_model_on_rec_sample.csv","odds_ratios_recommendation_model.csv"]}.items():
        for name in names:
            table=pd.read_csv(output_dir(part)/name)
            close(f"{part}/{name}: exp coefficients",table.odds_ratio,np.exp(table.coef_log_odds))
            close(f"{part}/{name}: Wald lower CIs",table.ci_low,np.exp(table.coef_log_odds-1.959963984540054*table.se_clustered))
            close(f"{part}/{name}: Wald upper CIs",table.ci_high,np.exp(table.coef_log_odds+1.959963984540054*table.se_clustered))
            if part=="F":
                price=table.model_term.str.startswith("C(price") & ~table.model_term.str.contains(":") | table.model_term.eq("log_price")
                check(f"{name}: conditional price interpretation",table.loc[price,"effect_context"].str.contains("Normal skin").all())
    for name in ["table1_price_or_across_specifications.csv","comparison_price_terms_five_star_vs_recommend.csv"]:
        table=pd.read_csv(output_dir("F")/name)
        check(f"{name}: Normal/Budget references",table.conditional_skin_type.eq("Normal").all() and table.reference_price.eq("Budget").all())
    split_data=[("five-star",df), ("recommendation",df[df.recommended.notna()])]
    from sklearn.model_selection import GroupShuffleSplit
    for name,sample in split_data:
        train,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=5106).split(sample,groups=sample.product_id))
        check(f"{name}: product-disjoint evaluation",set(sample.iloc[train].product_id).isdisjoint(set(sample.iloc[test].product_id)))
    report={"passed":all(c['passed'] for c in checks),"checks":checks,
            "seed":5106,"replicates":B,"minimum_bootstrap_group_reviews":minimum_denominator,
            "findings":{"overall_rate_pct":100*overall_point,"overall_ci_pct":(100*endpoints(overall_boot)).tolist(),
                        "icc":icc,
                        "product_weighted_overall_pct":100*means.mean(),"range_test_p":p_int,
                        "range_test_mc_se":float(np.sqrt(p_int*(1-p_int)/B)),"E_joint_wald_p":float(wald.wald_p)}}
    (RUN_DIR/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    for c in checks:
        print(('PASS ' if c['passed'] else 'FAIL ')+c['check'])
    print(json.dumps(report['findings'],indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':
    main()
