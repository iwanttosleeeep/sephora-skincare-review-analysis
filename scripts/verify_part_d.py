"""Independent product-multiplicity bootstrap audit and C/E/F consistency checks."""
import ast
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_paths import PART_C, PART_D, RESULTS_DIR, require_analysis

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
    checks, comparisons = [], []

    def check(name, condition, **detail):
        checks.append({"check": name, "passed": bool(condition), **detail})

    def close(name, actual, expected, atol=1e-10):
        actual, expected = np.asarray(actual), np.asarray(expected)
        check(name, actual.shape == expected.shape and np.allclose(actual, expected, atol=atol, rtol=1e-10),
              max_abs_difference=float(np.max(np.abs(actual-expected))))

    output = RESULTS_DIR / "part_d"
    tables = {p.stem: pd.read_csv(p) for p in output.glob("*.csv")}
    diag = json.loads((output / "diagnostics.json").read_text())
    with zipfile.ZipFile(ROOT / "preservation/part_d_original_submission.zip") as archive:
        manifest = json.loads((ROOT / "preservation/part_d_original_manifest.json").read_text())
        check("all original submission files preserved", all(
            hashlib.sha256(archive.read(x["path"])).hexdigest() == x["sha256"] for x in manifest))
        for item in manifest:
            name = item["path"]
            if not name.endswith(".csv"):
                continue
            original = pd.read_csv(io.BytesIO(archive.read(name)))
            current = tables[Path(name).stem]
            baseline = pd.read_csv(ROOT / "results/part_d_original_rerun/part_d" / Path(name).name)
            try:
                for other in [baseline, current]:
                    pd.testing.assert_frame_equal(original, other, check_dtype=False, atol=1e-10, rtol=1e-10)
                ok = True
                difference = float(np.max(np.abs(original.select_dtypes("number").to_numpy()
                                                 - current.select_dtypes("number").to_numpy())))
            except AssertionError as error:
                ok, difference = False, None
                comparisons.append({"file": Path(name).name, "passed": False, "detail": str(error)[:1500]})
            if ok:
                comparisons.append({"file": Path(name).name, "passed": True, "max_abs_difference": difference})
    check("all seven submitted CSVs reproduce before and after corrections", len(comparisons) == 7 and all(x["passed"] for x in comparisons))
    before = json.loads((ROOT / "preservation/part_d_pre_verification.json").read_text())
    check("input and other Part sources/results unchanged", all(
        hashlib.file_digest((ROOT / p).open("rb"), "sha256").hexdigest() == meta["sha256"] for p, meta in before.items()))
    df = pd.read_parquet(require_analysis(), columns=["product_id", "five_star", "rating", "price_segment", "category", "skin_type_cat", "recommended"])
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
    for key, label, levels, cfile in [("price_segment", "price_segment", PRICE, "step2_fsr_price_segment.csv"),
                                     ("skin_type_cat", "skin_type", SKIN, "step2_fsr_skin_type.csv"),
                                     ("category", "category", CATEGORY, "step2_fsr_category.csv")]:
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
        c = pd.read_csv(PART_C / cfile).set_index(key).loc[levels]
        close(f"{key}: Part C rates", c.five_star_pct, actual.five_star_rate_pct.round(2), atol=1e-12)
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
    c_cross = pd.read_csv(PART_C / "eda_by_price_skin.csv").set_index(["skin_type_cat", "price_segment"])
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
    close("recentred four-skin range test and plus-one p", [inter.statistic_range_pp, inter.p_value], [observed_range, p_int])
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
    book = json.loads((PART_D / "04_uncertainty_D.ipynb").read_text())
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
    wald=pd.read_csv(ROOT/'results/part_e/wald_interaction.csv').iloc[0]
    f_wald=pd.read_csv(ROOT/'results/part_f/table2_wald_tests.csv').iloc[0]
    close("E/F main-model Wald reference",[round(float(wald.wald_p),4)],[float(f_wald['p'])])
    check("distinct interaction hypotheses recorded", int(wald.wald_df)==12 and inter.skin_types=='Normal, Combination, Dry, Oily')
    e_or=pd.read_csv(ROOT/'results/part_e/odds_ratios_main_model.csv')
    check("E includes Not reported interactions", e_or.model_term.str.contains('Not reported',regex=False).sum()==4)
    e_auc=pd.read_csv(ROOT/'results/part_e/evaluation_metrics.csv').query("model == 'Main model'")['ROC-AUC'].iloc[0]
    f_auc=pd.read_csv(ROOT/'results/part_f/table4_held_out_evaluation.csv').iloc[0]['ROC-AUC']
    close("E/F main five-star evaluation reference",[round(e_auc,3)],[f_auc])
    check("F recommendation eligibility remains a separate outcome",df.recommended.notna().sum()==926031)
    check("no universal 200-review cap",int(overall_n.max())==16115 and (overall_n>200).any())
    execution=json.loads((RESULTS_DIR/'execution_d.json').read_text())
    check("Part D executed successfully on authoritative input", execution['steps'][0]['part']=='D' and execution['steps'][0]['exit_code']==0
          and execution['analysis_sha256']==hashlib.file_digest(require_analysis().open('rb'),'sha256').hexdigest())
    old_msb=(overall_n*(means-means.mean())**2).sum()/(P-1)
    old_msw=((overall_n-1)*means*(1-means)).sum()/(len(df)-P)
    report={"passed":all(c['passed'] for c in checks),"checks":checks,"original_csv_comparisons":comparisons,
            "seed":5106,"replicates":B,"minimum_bootstrap_group_reviews":minimum_denominator,
            "findings":{"overall_rate_pct":100*overall_point,"overall_ci_pct":(100*endpoints(overall_boot)).tolist(),
                        "corrected_icc":icc,"submitted_icc":(old_msb-old_msw)/(old_msb+(n0-1)*old_msw),
                        "submitted_wrong_overall_weighted_pct":100*group_results['price_segment']['points'].mean(),
                        "product_weighted_overall_pct":100*means.mean(),"range_test_p":p_int,
                        "range_test_mc_se":float(np.sqrt(p_int*(1-p_int)/B)),"E_joint_wald_p":float(wald.wald_p)}}
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    pd.DataFrame(comparisons).to_csv(output/'original_result_comparison.csv',index=False)
    for c in checks:
        print(('PASS ' if c['passed'] else 'FAIL ')+c['check'])
    print(json.dumps(report['findings'],indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':
    main()
