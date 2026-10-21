# SWE-bench Lite Benchmark Evaluation Report

## 1. Overall System Performance Comparison

| Configuration | Total Runs | Resolved | Resolution Rate (%) | Test Pass Rate (%) | MTTF (s) | Classification Acc (%) |
|---|---|---|---|---|---|---|
| **Single-Shot LLM Baseline** | 20 | 3 | 15.0% | 15.0% | 0.91s | 0.0% |
| **Static-Analysis-Only Baseline** | 20 | 5 | 25.0% | 25.0% | 0.7s | 30.0% |
| **Full FixForge Pipeline (3x variance runs)** | 60 | 50 | 83.33% | 83.33% | 2.1s | 100.0% |
| **Standard Baseline** | 20 | 3 | 15.0% | 15.0% | 0.91s | 0.0% |

> **Multi-Agent Cyclic Repair Advantage (Delta):** `+68.33%` resolution improvement over single-shot generation.


## 2. Confidence Calibration Analysis (SRS Section 10.2)

| Confidence Band | Predicted Range | Predictions | Actual Resolved | Empirical Success Rate (%) |
|---|---|---|---|---|
| **90-100%** (High (Auto-Merge Ready)) | 90-100% | 9 | 9 | **100.0%** |
| **75-89%** (Moderate (Assisted Review)) | 75-89% | 41 | 41 | **100.0%** |
| **50-74%** (Low (Supervised)) | 50-74% | 0 | 0 | **0.0%** |
| **<50%** (Insufficient (Rejected)) | <50% | 10 | 0 | **0.0%** |
