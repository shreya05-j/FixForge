# SWE-bench Lite Benchmark Evaluation Report

## 1. Overall System Performance Comparison

| Configuration | Total Runs | Resolved | Unverified | Fallback | Patch Failed | Failed | Resolution Rate (%) | Test Pass Rate (%) | MTTF (s) | Classification Acc (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Full FixForge Pipeline (3x variance runs)** | 60 | 50 | 0 | 0 | 0 | 10 | 83.33% | 83.33% | 2.09s | 100.0% |

## 2. Confidence Calibration Analysis (SRS Section 10.2)

| Confidence Band | Predicted Range | Predictions | Actual Resolved | Empirical Success Rate (%) |
|---|---|---|---|---|
| **90-100%** (High (Auto-Merge Ready)) | 90-100% | 9 | 9 | **100.0%** |
| **75-89%** (Moderate (Assisted Review)) | 75-89% | 41 | 41 | **100.0%** |
| **50-74%** (Low (Supervised)) | 50-74% | 0 | 0 | **0.0%** |
| **<50%** (Insufficient (Rejected)) | <50% | 10 | 0 | **0.0%** |
