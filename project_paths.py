"""Shared paths. No downloads or implicit upstream regeneration."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PART_A = ROOT / "Part A."
PART_B = ROOT / "Part B. Data Cleaning & Feature Engineering"
PART_C = ROOT / "Part C. Exploratory Data Analysis & Visualization"
PART_D = ROOT / "Part D. Statistical Uncertainty & Visualization"
PART_E = ROOT / "Part E. Main Modeling & Evaluation"
PART_F = ROOT / "Part F. Secondary Outcome and Sensitivity Analysis"
DATA_DIR = Path(os.environ.get("SEPHORA_DATA_DIR", ROOT / "data")).expanduser().resolve()
RAW_DIR = Path(os.environ.get("SEPHORA_RAW_DIR", DATA_DIR / "raw")).expanduser().resolve()
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_PATH = Path(os.environ.get(
    "SEPHORA_ANALYSIS_PATH", PART_B / "data/processed/analysis_ready.parquet"
)).expanduser().resolve()
RESULTS_DIR = Path(os.environ.get("SEPHORA_RESULTS_DIR", ROOT / "results")).expanduser().resolve()


def require_analysis():
    if not ANALYSIS_PATH.is_file():
        raise FileNotFoundError(
            f"Authoritative processed dataset missing: {ANALYSIS_PATH}. "
            "Set SEPHORA_ANALYSIS_PATH to an available analysis_ready.parquet. "
            "No data will be downloaded or regenerated."
        )
    return ANALYSIS_PATH


def require_merged():
    override = os.environ.get("SEPHORA_MERGED_PATH")
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"SEPHORA_MERGED_PATH does not exist: {path}")
        return path
    candidates = [PROCESSED_DIR / "merged_reviews.parquet",
                  PART_A / "merged_reviews.parquet",
                  ROOT / "merged_reviews.parquet",
                  PART_A / "data/processed/merged_reviews.parquet",
                  PART_B / "data/processed/merged_reviews.parquet"]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "merged_reviews.parquet is intentionally not distributed in Git (~219 MB). "
        "Part B can only be rerun when it is supplied or Part A is explicitly rerun "
        "with all six raw CSVs. Parts C–F use analysis_ready.parquet independently."
    )
