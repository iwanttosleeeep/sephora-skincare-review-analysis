"""Repository paths and explicit local dataset selection; no downloads."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PART_FOLDERS = {
    "A": "part_a_data_integration",
    "B": "part_b_data_cleaning",
    "C": "part_c_exploratory_analysis",
    "D": "part_d_statistical_uncertainty",
    "E": "part_e_main_modeling",
    "F": "part_f_secondary_analysis",
}
PART_A, PART_B, PART_C, PART_D, PART_E, PART_F = (ROOT / PART_FOLDERS[p] for p in "ABCDEF")
DATA_DIR = Path(os.environ.get("SEPHORA_DATA_DIR", ROOT / "data")).expanduser().resolve()
RAW_DIR = Path(os.environ.get("SEPHORA_RAW_DIR", DATA_DIR / "raw")).expanduser().resolve()
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_PATH = Path(os.environ.get("SEPHORA_ANALYSIS_PATH", PROCESSED_DIR / "analysis_ready.parquet")).expanduser().resolve()
RESULTS_DIR = Path(os.environ.get("SEPHORA_RESULTS_DIR", ROOT)).expanduser().resolve()
RUN_DIR = ROOT / ".run"


def output_dir(part):
    return RESULTS_DIR / PART_FOLDERS[part.upper()] / "outputs"


def require_analysis():
    if not ANALYSIS_PATH.is_file():
        raise FileNotFoundError(
            f"Supply analysis_ready.parquet at {ANALYSIS_PATH} or set SEPHORA_ANALYSIS_PATH. "
            "Alternatively run A/B explicitly with manually supplied raw CSVs. No download is performed."
        )
    return ANALYSIS_PATH


def require_merged():
    path = Path(os.environ.get("SEPHORA_MERGED_PATH", PROCESSED_DIR / "merged_reviews.parquet")).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"Supply merged_reviews.parquet at {path} or set SEPHORA_MERGED_PATH, "
            "or run A explicitly. Large intermediate data are intentionally excluded from Git."
        )
    return path
