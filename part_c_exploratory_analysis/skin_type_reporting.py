"""Descriptive reporting-status checks using full-dataset author review counts."""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from project_paths import output_dir, require_analysis

GROUPS = ["Not reported", "Reported"]
PERIODS = ["Before 2017", "2017 onward"]


def build_reporting_tables(data):
    """Return three summaries; expectation flags describe, rather than hide, mismatches.

    An author can belong to both reporting groups. Review-weighted medians attach
    each author's total review count to every review; author-weighted medians
    count each distinct author once within each reporting group. Both use the
    full input dataset to count reviews, before any group or period filtering.
    """
    columns = ["author_id", "skin_type_cat", "review_year", "five_star"]
    frame = data[columns].copy()
    if frame.empty or frame[columns].isna().any().any():
        raise ValueError("Reporting checks require nonempty data and complete author/year/skin/outcome fields.")
    if not frame.five_star.isin([0, 1]).all():
        raise ValueError("five_star must be binary.")
    if not frame.skin_type_cat.isin(["Normal", "Combination", "Dry", "Oily", "Not reported"]).all():
        raise ValueError("Unexpected processed skin-type label.")
    years = pd.to_numeric(frame.review_year, errors="raise")
    if years.mod(1).ne(0).any():
        raise ValueError("review_year must contain integer years.")
    frame["review_year"] = years.astype("int64")
    frame["not_reported"] = frame.skin_type_cat.eq("Not reported")
    frame["skin_type_reporting"] = frame.not_reported.map({True: "Not reported", False: "Reported"})

    # Count over the full dataset, not within a reporting group or year period.
    author_counts = frame.groupby("author_id", observed=True).size()
    frame["author_reviews_full_dataset"] = frame.author_id.map(author_counts)

    yearly = frame.groupby("review_year", observed=True).agg(
        n_reviews=("five_star", "size"), n_not_reported=("not_reported", "sum")
    ).reset_index()
    yearly["n_reported"] = yearly.n_reviews - yearly.n_not_reported
    yearly["not_reported_share_pct"] = 100 * yearly.n_not_reported / yearly.n_reviews
    yearly["expected_rule"] = "Not specified"
    yearly["matches_expected"] = pd.Series(pd.NA, index=yearly.index, dtype="boolean")
    early = yearly.review_year.between(2012, 2017)
    yearly.loc[early, "expected_rule"] = "29–51% at nearest whole-percent precision"
    yearly.loc[early, "matches_expected"] = yearly.loc[early, "not_reported_share_pct"].round().between(29, 51)
    recent = yearly.review_year.ge(2018)
    yearly.loc[recent, "expected_rule"] = "Under 2%"
    yearly.loc[recent, "matches_expected"] = yearly.loc[recent, "not_reported_share_pct"].lt(2)

    activity = frame.groupby("skin_type_reporting", observed=True).agg(
        n_reviews=("five_star", "size"),
        n_authors=("author_id", "nunique"),
        median_author_reviews_review_weighted=("author_reviews_full_dataset", "median"),
    ).reindex(GROUPS)
    author_group = frame.drop_duplicates(["author_id", "skin_type_reporting"])
    activity["median_author_reviews_author_weighted"] = author_group.groupby(
        "skin_type_reporting", observed=True
    ).author_reviews_full_dataset.median().reindex(GROUPS)
    activity["expected_review_weighted_median"] = [1, 3]
    activity["matches_expected_review_weighted"] = activity.median_author_reviews_review_weighted.eq(
        activity.expected_review_weighted_median
    )
    activity = activity.reset_index()

    frame["period"] = frame.review_year.lt(2017).map({True: PERIODS[0], False: PERIODS[1]})
    period = frame.groupby(["period", "skin_type_reporting"], observed=True).agg(
        n_reviews=("five_star", "size"), n_authors=("author_id", "nunique"),
        n_five_star=("five_star", "sum"),
    ).reindex(pd.MultiIndex.from_product([PERIODS, GROUPS], names=["period", "skin_type_reporting"]))
    period["five_star_rate_pct"] = 100 * period.n_five_star / period.n_reviews
    period["expected_five_star_rate_pct"] = [67.5, 66.5, 63.7, 63.4]
    period["matches_expected_one_decimal"] = period.five_star_rate_pct.round(1).eq(period.expected_five_star_rate_pct)
    period = period.reset_index()
    period["review_year_rule"] = period.period.map({PERIODS[0]: "<2017", PERIODS[1]: ">=2017"})

    assert yearly.n_reviews.sum() == len(frame)
    assert activity.n_reviews.sum() == len(frame)
    assert period.n_reviews.sum() == len(frame)
    assert period.n_five_star.sum() == frame.five_star.sum()
    return {
        "skin_type_not_reported_by_year.csv": yearly,
        "skin_type_author_activity.csv": activity,
        "skin_type_five_star_by_period.csv": period,
    }


def save_reporting_tables(tables, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(destination / name, index=False)


def main():
    data = pd.read_parquet(require_analysis(), columns=["author_id", "skin_type_cat", "review_year", "five_star"])
    tables = build_reporting_tables(data)
    save_reporting_tables(tables, output_dir("C"))
    for name, table in tables.items():
        print(f"\n{name}\n{table.to_string(index=False)}")
    recent = tables["skin_type_not_reported_by_year.csv"].query("review_year >= 2018")
    print(f"\nPooled 2018 onward Not reported share: {100*recent.n_not_reported.sum()/recent.n_reviews.sum():.2f}%")
    print("\nExpectation flags retain any departures. Author totals always use the full dataset.")


if __name__ == "__main__":
    main()
