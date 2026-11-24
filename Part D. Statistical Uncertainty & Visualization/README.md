# Part D — Statistical uncertainty and visualization

From the project root, with the documented environment installed:

```bash
python scripts/run_analysis.py --parts D
python scripts/verify_part_d.py
```

The default full downstream run executes C, E, D, F so E's prediction table is available before D. Shared paths work from the root or a Part folder. The usual `SEPHORA_ANALYSIS_PATH` and `SEPHORA_RESULTS_DIR` overrides apply. D-only execution writes `results/execution_d.json`, preserving the prior C/E/F execution record.

Current outputs are in `results/part_d/`: seven original-format CSVs, five figures, weighting/ICC diagnostics and independent verification. Seed 5106, 2,000 replicates, review weighting, percentile intervals, paired contrasts and the four-reported-skin interaction test are unchanged. All seven original CSVs reproduce.

The original submission is preserved byte-for-byte in `preservation/part_d_original_submission.zip`, with hashes in `part_d_original_manifest.json`. The supplied `outputs/`, HTML export and Word draft remain unchanged historical snapshots. **Use the corrected notebook, current results and corrected Markdown notes for current findings.** The historical HTML/Word contain the original calculation and interpretation errors described in `docs/REVIEW.md`; they have not been regenerated as final submission documents.

Technical fixes cover the ICC sums of squares, an incorrect displayed overall rate, plotting bounds and a wrongly oriented connector. `verify_part_d.py` independently computes product multiplicities, paired percentile intervals and the recentred range test, verifies a literal review-expansion example, and reconciles C/E/F artifacts.

Intervals are pointwise/nominal, without multiplicity adjustment. `boot_p` fields are percentile-tail approximations. D and E test different interaction hypotheses. See the root review and corrected notes for limitations.

For an optional independent rerun of the archived original, use `python scripts/reproduce_original_part_d.py --output-dir <new-directory>`. Only input/output paths are substituted; the archived statistical code is unchanged.
