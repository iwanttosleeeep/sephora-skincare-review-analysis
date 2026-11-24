"""Run the research pipeline; default C/E/D/F, with A/B explicitly enabled."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from project_paths import PART_A, PART_B, PART_C, PART_D, PART_E, PART_F, RUN_DIR, require_analysis

NOTEBOOKS = {
    "A": PART_A / "01_data_integration.ipynb",
    "B": PART_B / "02_data_cleaning.ipynb",
    "C": PART_C / "03_exploratory_analysis.ipynb",
    "D": PART_D / "04_statistical_uncertainty.ipynb",
    "E": PART_E / "05_main_modeling.ipynb",
}


def execute_notebook(path):
    import nbformat
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output

    book = nbformat.read(path, as_version=4)
    shell = InteractiveShell.instance()
    shell.user_ns["__name__"] = "__main__"
    target = RUN_DIR / "executed" / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    for index, cell in enumerate(book.cells):
        if cell.cell_type != "code":
            continue
        print(f"{path.name}: cell {index}", flush=True)
        with capture_output() as captured:
            result = shell.run_cell(cell.source, store_history=True)
        cell.outputs = []
        for stream in ["stdout", "stderr"]:
            value = getattr(captured, stream)
            if value:
                print(value, end="", file=sys.stderr if stream == "stderr" else sys.stdout)
                cell.outputs.append(nbformat.v4.new_output("stream", name=stream, text=value))
        for item in captured.outputs:
            cell.outputs.append(nbformat.v4.new_output("display_data", data=item.data, metadata=item.metadata))
        cell.execution_count = shell.execution_count - 1
        nbformat.write(book, target)
        if result.error_before_exec or result.error_in_exec:
            raise RuntimeError(f"{path.name}: cell {index} failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts", nargs="+", choices=list("ABCDEF"), default=list("CEDF"))
    parser.add_argument("--include-upstream", action="store_true", help="Enable A/B using manually supplied inputs")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        if args.worker.suffix == ".ipynb":
            execute_notebook(args.worker)
        else:
            import runpy
            runpy.run_path(str(args.worker), run_name="__main__")
        return
    if set(args.parts) & set("AB") and not args.include_upstream:
        parser.error("A/B require --include-upstream and manually supplied inputs.")
    # E's adjusted prediction table is an input to D's descriptive comparison.
    parts = [p for p in "ABCEDF" if p in args.parts]
    fingerprint = None
    if set(parts) & set("CDEF") and not set(parts) & set("AB"):
        with require_analysis().open("rb") as stream:
            fingerprint = hashlib.file_digest(stream, "sha256").hexdigest()
    log_dir = RUN_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"MPLBACKEND": "Agg", "MPLCONFIGDIR": str(RUN_DIR / "matplotlib"),
                "IPYTHONDIR": str(RUN_DIR / "ipython"), "PYTHONHASHSEED": "5106",
                "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"})
    report = {"parts": parts, "analysis_sha256": fingerprint, "python": sys.version.split()[0],
              "packages": {name: importlib.metadata.version(name) for name in
                           ["numpy", "pandas", "pyarrow", "scipy", "statsmodels", "scikit-learn"]}, "steps": []}
    for part in parts:
        if part in "CDEF" and fingerprint is None:
            with require_analysis().open("rb") as stream:
                fingerprint = hashlib.file_digest(stream, "sha256").hexdigest()
            report["analysis_sha256"] = fingerprint
        paths = [NOTEBOOKS[part]] if part != "F" else [PART_F / name for name in
                 ["recommendation_analysis.py", "log_price_sensitivity.py", "model_comparison.py"]]
        for path in paths:
            log = log_dir / f"{path.stem}.log"
            print(f"Running {part}: {path.name}", flush=True)
            with log.open("w") as stream:
                status = subprocess.run([sys.executable, __file__, "--worker", str(path)], cwd=ROOT, env=env,
                                        stdout=stream, stderr=subprocess.STDOUT)
            report["steps"].append({"part": part, "source": str(path.relative_to(ROOT)), "exit_code": status.returncode})
            (RUN_DIR / "execution.json").write_text(json.dumps(report, indent=2) + "\n")
            if status.returncode:
                raise SystemExit(f"Execution failed; see {log}")
    if fingerprint:
        with require_analysis().open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == fingerprint
    print("Pipeline completed; existing analysis input unchanged.")


if __name__ == "__main__":
    main()
