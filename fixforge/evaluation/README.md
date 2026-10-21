# FixForge Evaluation Benchmark

## 1. Dataset Selection Methodology
The FixForge benchmark evaluation set consists of **20 real-world defect instances** sourced and curated from representative open-source Python repositories in SWE-bench Lite and established Python libraries (`pallets/flask`, `psf/requests`, `pytest-dev/pytest`, `django/django`, `sympy/sympy`, `scikit-learn`, `sqlfluff`, `fastapi`, `aiohttp`, etc.).

### Selection Criteria:
1. **Diverse Failure Modes**: The 20 instances represent 5 distinct failure categories:
   - **Runtime Error** (e.g. Unhandled `TypeError`, `ZeroDivisionError`, `RecursionError`)
   - **Logic Error** (e.g. Regex boundary failure, invalid state check, key sensitivity)
   - **Type Error** (e.g. Dimensionality mismatch, missing nested dict fields)
   - **Syntax Error** (e.g. Parser token failure, query parameter alias format error)
   - **Resource Leak** (e.g. Async generator unclosed warning, unclosed connection)
2. **Reproducible Held-Out Verification**: Each instance specifies target source files, problem statements, expected classification, candidate ground-truth patches, and deterministic held-out test commands.
3. **No Synthetic Shortcuts**: Real codebase structure and multi-file dependencies are preserved.

---

## 2. Benchmark Configurations
Three distinct configurations are evaluated against all 20 benchmark instances:

1. **Single-Shot LLM Baseline**:
   - Single prompt to the LLM requesting a unified diff without AST context retrieval, fault diagnosis, or sandbox retry feedback.
2. **Static-Analysis-Only Baseline**:
   - Analyzes code using static linter rules (Pyflakes / AST checks) to assess patch correctness without containerized sandbox execution or dynamic test pass feedback.
3. **Full FixForge Pipeline**:
   - 7-node LangGraph cyclic workflow: Planner $\to$ Retriever (AST symbol extraction) $\to$ Diagnoser $\to$ Fixer $\to$ Verifier (Docker/pytest sandbox with up to 3 retry loops) $\to$ Confidence Engine (multi-signal weighted scoring) $\to$ Reporter.
   - Run **3 times per instance** to measure statistical variance and repeatability.

---

## 3. Metrics Reported
- **Resolution Rate (%)**: Percentage of instances where the generated patch passes held-out test verification.
- **Test Pass Rate (%)**: Ratio of individual test cases passing in the verification environment.
- **Mean Time to Fix (MTTF in seconds)**: Average wall-clock latency to produce and verify a candidate fix.
- **Classification Accuracy (%)**: Agreement between FixForge's Diagnoser and ground-truth failure categories.
- **Confidence Calibration Table**: Correlation between predicted SRS 10.2 confidence bands and empirical success rates.

---

## 4. How to Reproduce
Run the benchmark directly from the repository root:
```bash
python -m evaluation.run_benchmark
```
Or execute the automated Stage 6 verification test suite:
```bash
pytest fixforge/tests/test_evaluation_stage6.py -v
```
Results will be exported to:
- `results/benchmark_results.csv` (Raw per-instance results across all runs)
- `results/benchmark_report.md` (Markdown summary tables)
- `results/benchmark_summary.json` (Structured JSON metrics and deltas)
