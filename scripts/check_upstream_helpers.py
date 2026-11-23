"""Exercise isolated A/B cleaning helpers on synthetic data, without upstream files."""
import ast
from difflib import SequenceMatcher
import io
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_paths import PART_A, PART_B


def cells(folder):
    return [ast.parse("".join(c["source"])) for c in json.loads(next(folder.glob("*.ipynb")).read_text())["cells"]
            if c["cell_type"] == "code"]


def main():
    a, b = cells(PART_A), cells(PART_B)
    namespace = {"pd": pd, "ast": ast, "conversion_issues": [],
                 "missing_tokens": ["", "nan", "none", "null", "n/a", "na"]}
    for module in a + b:
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name in {
                "clean_string_columns", "convert_numeric_columns", "convert_boolean_columns", "parse_tags", "norm_text"
            }:
                exec(compile(ast.Module(body=[node], type_ignores=[]), "notebook helper", "exec"), namespace)

    frame = pd.DataFrame({"s": ["  Normal ", "N/A", None]})
    cleaned = namespace["clean_string_columns"](frame, ["s"])
    assert cleaned.s.iloc[0] == "Normal" and cleaned.s.isna().sum() == 2
    frame = pd.DataFrame({"n": ["2", "2.5", "bad", None]})
    converted = namespace["convert_numeric_columns"](frame, ["n"], "fixture", "Int64")
    assert converted.n.iloc[1] == 2.5 and converted.n.isna().sum() == 2
    assert namespace["conversion_issues"][-1]["fractional_values_in_integer_column"] == 1
    frame = pd.DataFrame({"b": ["TRUE", "0", "1.0", "invalid", None]})
    converted = namespace["convert_boolean_columns"](frame, ["b"], "fixture")
    assert converted.b.iloc[:3].tolist() == [True, False, True] and converted.b.isna().sum() == 2
    parse = namespace["parse_tags"]
    assert parse("['Vegan', ' Fragrance Free ']") == ["Vegan", "Fragrance Free"]
    assert parse(None) is None and parse(pd.NA) is None
    for malformed in ["not a list", "'Vegan'", "{'Vegan': 1}", "[1, 'Vegan']"]:
        try:
            parse(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Malformed highlights accepted: {malformed}")

    # Use the actual dtype keyword from A's CSV read expression.
    read_call = next(node for module in a for node in ast.walk(module)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                     and node.func.attr == "read_csv")
    dtype = ast.literal_eval(next(k.value for k in read_call.keywords if k.arg == "dtype"))
    fixture = pd.read_csv(io.StringIO("product_id,author_id\nP1,00012\nP2,1234567890123456789\n"), dtype=dtype)
    assert fixture.author_id.tolist() == ["00012", "1234567890123456789"]

    # Run only the original same-day comparison loop on a small synthetic table.
    dedup_loop = next(node for module in b for node in module.body
                     if isinstance(node, ast.For) and "same_day.groupby" in ast.unparse(node.iter))
    namespace.update({"same_day": pd.DataFrame({"author_id": ["A"]*4, "product_id": ["P"]*4,
                        "submission_time": ["2023-01-01"]*4, "review_id": [1,2,3,4],
                        "review_text": [None, None, "Love this product", "Love this product"]}),
                      "same_day_key": ["author_id", "product_id", "submission_time"],
                      "SequenceMatcher": SequenceMatcher, "TEXT_SIM_THRESHOLD": .9,
                      "resubmission_ids": [], "sims": []})
    exec(compile(ast.Module(body=[dedup_loop], type_ignores=[]), "same-day fixture", "exec"), namespace)
    assert namespace["resubmission_ids"] == [4], "Missing text must not itself trigger removal"
    print("PASS isolated A/B helpers: string normalization, numeric/Boolean coercion, exact IDs, highlight parsing, missing-text deduplication")
    print("Synthetic fixtures only; A/B raw-data pipeline was not executed.")


if __name__ == "__main__":
    main()
