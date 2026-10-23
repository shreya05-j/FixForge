# FixForge Live Benchmark Evaluation Report

**Date**: 2026-10-22 19:37 UTC  

**Model**: `qwen/qwen3.8-27b`  

**Benchmark**: Curated Real-Style Bug Benchmark — 20 instances (NOT official SWE-bench Lite harness)  

**Branch**: `live-mode-hardening`  


> [!CAUTION]
> Resolution = `docker_status=='passed'` AND `test_passed==True` AND all `agent_sources=='llm'`.
> Unverified / fallback / patch_failed results appear in separate columns and cannot count as resolved.

## 1. Overall System Performance Comparison

| Configuration | Total Runs | Resolved | Unverified | Fallback | Patch Failed | Failed | Resolution Rate (%) | MTTF (s) | Classification Acc (%) |
|---|---|---|---|---|---|---|---|---|---|
| **Single-Shot LLM Baseline** | 20 | 0 | 0 | 1 | 0 | 20 | 0.0% | 11.45s | 0.0% |
| **Static-Analysis-Only Baseline** | 20 | 0 | 0 | 0 | 0 | 0 | 0.0% | 0.16s | 100.0% |
| **Full FixForge Pipeline** | 60 | 0 | 60 | 0 | 0 | 0 | 0.0% | 440.85s | 30.0% |

> **Multi-Agent vs Single-Shot Delta:** `+0.0%` resolution improvement.


## 2. Confidence Calibration

| Band | Range | Predictions | Resolved | Empirical Success (%) |
|---|---|---|---|---|
| **90-100%** | High | 0 | 0 | **0.0%** |
| **75-89%** | Moderate | 0 | 0 | **0.0%** |
| **50-74%** | Low | 0 | 0 | **0.0%** |
| **<50%** | Insufficient | 60 | 0 | **0.0%** |

## 3. Per-Instance Results (FixForge Pipeline)

| Instance | Run | Status | Docker | Agent Sources | Tokens | Latency (s) | Retries | Pred Classification |
|---|---|---|---|---|---|---|---|---|
| `aio-libs__aiohttp-4100` | 1 | unverified | unverified | llm,llm,llm | 1605 | 11571.52 | 0 | Runtime Error |
| `aio-libs__aiohttp-4100` | 2 | unverified | unverified | llm,llm,llm | 1605 | 63.3 | 0 | Runtime Error |
| `aio-libs__aiohttp-4100` | 3 | unverified | unverified | llm,llm,llm | 1605 | 62.89 | 0 | Runtime Error |
| `django__django-11099` | 1 | unverified | unverified | llm,llm,llm | 1515 | 74.85 | 0 | Logic Error |
| `django__django-11099` | 2 | unverified | unverified | llm,llm,llm | 1515 | 62.8 | 0 | Logic Error |
| `django__django-11099` | 3 | unverified | unverified | llm,llm,llm | 1515 | 63.37 | 0 | Logic Error |
| `django__django-12856` | 1 | unverified | unverified | llm,llm,llm | 1508 | 63.32 | 0 | Dependency Error |
| `django__django-12856` | 2 | unverified | unverified | llm,llm,llm | 1508 | 63.53 | 0 | Dependency Error |
| `django__django-12856` | 3 | unverified | unverified | llm,llm,llm | 1508 | 63.15 | 0 | Dependency Error |
| `fastapi__fastapi-2451` | 1 | unverified | unverified | llm,llm,llm | 1499 | 63.04 | 0 | Logic Error |
| `fastapi__fastapi-2451` | 2 | unverified | unverified | llm,llm,llm | 1499 | 63.86 | 0 | Logic Error |
| `fastapi__fastapi-2451` | 3 | unverified | unverified | llm,llm,llm | 1499 | 63.9 | 0 | Logic Error |
| `marshmallow-code__marshmallow-` | 1 | unverified | unverified | llm,llm,llm | 1576 | 64.91 | 0 | Logic Error |
| `marshmallow-code__marshmallow-` | 2 | unverified | unverified | llm,llm,llm | 1576 | 63.24 | 0 | Logic Error |
| `marshmallow-code__marshmallow-` | 3 | unverified | unverified | llm,llm,llm | 1576 | 63.29 | 0 | Logic Error |
| `pallets__flask-5012` | 1 | unverified | unverified | llm,llm,llm | 1615 | 94.91 | 0 | Runtime Error |
| `pallets__flask-5012` | 2 | unverified | unverified | llm,llm,llm | 1615 | 93.35 | 0 | Runtime Error |
| `pallets__flask-5012` | 3 | unverified | unverified | llm,llm,llm | 1615 | 68.65 | 0 | Runtime Error |
| `pallets__jinja-1208` | 1 | unverified | unverified | llm,llm,llm | 1477 | 63.34 | 0 | Logic Error |
| `pallets__jinja-1208` | 2 | unverified | unverified | llm,llm,llm | 1477 | 63.59 | 0 | Logic Error |
| `pallets__jinja-1208` | 3 | unverified | unverified | llm,llm,llm | 1477 | 62.88 | 0 | Logic Error |
| `pallets__werkzeug-1387` | 1 | unverified | unverified | llm,llm,llm | 1519 | 63.93 | 0 | Logic Error |
| `pallets__werkzeug-1387` | 2 | unverified | unverified | llm,llm,llm | 1519 | 63.24 | 0 | Logic Error |
| `pallets__werkzeug-1387` | 3 | unverified | unverified | llm,llm,llm | 1519 | 62.81 | 0 | Logic Error |
| `psf__requests-1724` | 1 | unverified | unverified | llm,llm,llm | 1586 | 93.64 | 0 | Runtime Error |
| `psf__requests-1724` | 2 | unverified | unverified | llm,llm,llm | 1586 | 62.69 | 0 | Runtime Error |
| `psf__requests-1724` | 3 | unverified | unverified | llm,llm,llm | 1586 | 63.72 | 0 | Runtime Error |
| `psf__requests-2148` | 1 | unverified | unverified | llm,llm,llm | 943 | 142.02 | 0 | Runtime Error |
| `psf__requests-2148` | 2 | unverified | unverified | llm,llm,llm | 943 | 68.18 | 0 | Runtime Error |
| `psf__requests-2148` | 3 | unverified | unverified | llm,llm,llm | 943 | 66.17 | 0 | Runtime Error |
| `pylint-dev__pylint-4630` | 1 | unverified | unverified | llm,llm,llm | 1613 | 66.1 | 0 | Dependency Error |
| `pylint-dev__pylint-4630` | 2 | unverified | unverified | llm,llm,llm | 1613 | 67.23 | 0 | Dependency Error |
| `pylint-dev__pylint-4630` | 3 | unverified | unverified | llm,llm,llm | 1613 | 63.06 | 0 | Dependency Error |
| `pytest-dev__pytest-5221` | 1 | unverified | unverified | llm,llm,llm | 1517 | 70.69 | 0 | Logic Error |
| `pytest-dev__pytest-5221` | 2 | unverified | unverified | llm,llm,llm | 1517 | 63.0 | 0 | Logic Error |
| `pytest-dev__pytest-5221` | 3 | unverified | unverified | llm,llm,llm | 1517 | 63.13 | 0 | Logic Error |
| `pytest-dev__pytest-7168` | 1 | unverified | unverified | llm,llm,llm | 1567 | 63.86 | 0 | Runtime Error |
| `pytest-dev__pytest-7168` | 2 | unverified | unverified | llm,llm,llm | 1567 | 63.2 | 0 | Runtime Error |
| `pytest-dev__pytest-7168` | 3 | unverified | unverified | llm,llm,llm | 1567 | 63.05 | 0 | Runtime Error |
| `scikit-learn__scikit-learn-102` | 1 | unverified | unverified | llm,llm,llm | 1559 | 62.85 | 0 | Logic Error |
| `scikit-learn__scikit-learn-102` | 2 | unverified | unverified | llm,llm,llm | 1559 | 124.0 | 0 | Logic Error |
| `scikit-learn__scikit-learn-102` | 3 | unverified | unverified | llm,llm,llm | 1559 | 62.86 | 0 | Logic Error |
| `scikit-learn__scikit-learn-110` | 1 | unverified | unverified | llm,llm,llm | 1654 | 82.92 | 0 | Logic Error |
| `scikit-learn__scikit-learn-110` | 2 | unverified | unverified | llm,llm,llm | 1654 | 63.69 | 0 | Logic Error |
| `scikit-learn__scikit-learn-110` | 3 | unverified | unverified | llm,llm,llm | 1654 | 66.5 | 0 | Logic Error |
| `sphinx-doc__sphinx-8714` | 1 | unverified | unverified | llm,llm,llm | 1457 | 62.99 | 0 | Logic Error |
| `sphinx-doc__sphinx-8714` | 2 | unverified | unverified | llm,llm,llm | 1457 | 572.53 | 0 | Logic Error |
| `sphinx-doc__sphinx-8714` | 3 | unverified | unverified | llm,llm,llm | 1457 | 92.9 | 0 | Logic Error |
| `sqlfluff__sqlfluff-1733` | 1 | unverified | unverified | llm,llm,llm | 1652 | 87.88 | 0 | Logic Error |
| `sqlfluff__sqlfluff-1733` | 2 | unverified | unverified | llm,llm,llm | 1652 | 64.76 | 0 | Logic Error |
| `sqlfluff__sqlfluff-1733` | 3 | unverified | unverified | llm,llm,llm | 1652 | 63.94 | 0 | Logic Error |
| `sympy__sympy-13480` | 1 | unverified | unverified | llm,llm,llm | 1768 | 10323.2 | 0 | Logic Error |
| `sympy__sympy-13480` | 2 | unverified | unverified | llm,llm,llm | 1768 | 70.61 | 0 | Logic Error |
| `sympy__sympy-13480` | 3 | unverified | unverified | llm,llm,llm | 1768 | 63.67 | 0 | Logic Error |
| `sympy__sympy-15345` | 1 | unverified | unverified | llm,llm,llm | 1637 | 67.19 | 0 | Logic Error |
| `sympy__sympy-15345` | 2 | unverified | unverified | llm,llm,llm | 1637 | 63.43 | 0 | Logic Error |
| `sympy__sympy-15345` | 3 | unverified | unverified | llm,llm,llm | 1637 | 63.01 | 0 | Logic Error |
| `urllib3__urllib3-1456` | 1 | unverified | unverified | llm,llm,llm | 1647 | 63.79 | 0 | Logic Error |
| `urllib3__urllib3-1456` | 2 | unverified | unverified | llm,llm,llm | 1647 | 64.61 | 0 | Logic Error |
| `urllib3__urllib3-1456` | 3 | unverified | unverified | llm,llm,llm | 1647 | 76.13 | 0 | Logic Error |

## 4. Failure Analysis

| Instance | Failure Category | Reason |
|---|---|---|
| `pallets__flask-5012` | unverified | unverified |
| `pytest-dev__pytest-5221` | unverified | unverified |
| `django__django-11099` | unverified | unverified |
| `sympy__sympy-13480` | unverified | unverified |
| `marshmallow-code__marshmallow-` | unverified | unverified |
| `psf__requests-2148` | unverified | unverified |
| `scikit-learn__scikit-learn-102` | unverified | unverified |
| `sqlfluff__sqlfluff-1733` | unverified | unverified |
| `pylint-dev__pylint-4630` | unverified | unverified |
| `pallets__jinja-1208` | unverified | unverified |
| `psf__requests-1724` | unverified | unverified |
| `django__django-12856` | unverified | unverified |
| `pytest-dev__pytest-7168` | unverified | unverified |
| `sympy__sympy-15345` | unverified | unverified |
| `urllib3__urllib3-1456` | unverified | unverified |
| `fastapi__fastapi-2451` | unverified | unverified |
| `pallets__werkzeug-1387` | unverified | unverified |
| `scikit-learn__scikit-learn-110` | unverified | unverified |
| `aio-libs__aiohttp-4100` | unverified | unverified |
| `sphinx-doc__sphinx-8714` | unverified | unverified |
| `pallets__flask-5012` | unverified | unverified |
| `psf__requests-2148` | unverified | unverified |
| `pytest-dev__pytest-5221` | unverified | unverified |
| `django__django-11099` | unverified | unverified |
| `sympy__sympy-13480` | unverified | unverified |
| `marshmallow-code__marshmallow-` | unverified | unverified |
| `scikit-learn__scikit-learn-102` | unverified | unverified |
| `sqlfluff__sqlfluff-1733` | unverified | unverified |
| `pylint-dev__pylint-4630` | unverified | unverified |
| `pallets__jinja-1208` | unverified | unverified |
| `psf__requests-1724` | unverified | unverified |
| `django__django-12856` | unverified | unverified |
| `pytest-dev__pytest-7168` | unverified | unverified |
| `sympy__sympy-15345` | unverified | unverified |
| `urllib3__urllib3-1456` | unverified | unverified |
| `fastapi__fastapi-2451` | unverified | unverified |
| `pallets__werkzeug-1387` | unverified | unverified |
| `scikit-learn__scikit-learn-110` | unverified | unverified |
| `aio-libs__aiohttp-4100` | unverified | unverified |
| `sphinx-doc__sphinx-8714` | unverified | unverified |
| `pallets__flask-5012` | unverified | unverified |
| `psf__requests-2148` | unverified | unverified |
| `pytest-dev__pytest-5221` | unverified | unverified |
| `django__django-11099` | unverified | unverified |
| `sympy__sympy-13480` | unverified | unverified |
| `marshmallow-code__marshmallow-` | unverified | unverified |
| `scikit-learn__scikit-learn-102` | unverified | unverified |
| `sqlfluff__sqlfluff-1733` | unverified | unverified |
| `pylint-dev__pylint-4630` | unverified | unverified |
| `pallets__jinja-1208` | unverified | unverified |
| `psf__requests-1724` | unverified | unverified |
| `django__django-12856` | unverified | unverified |
| `pytest-dev__pytest-7168` | unverified | unverified |
| `sympy__sympy-15345` | unverified | unverified |
| `urllib3__urllib3-1456` | unverified | unverified |
| `fastapi__fastapi-2451` | unverified | unverified |
| `pallets__werkzeug-1387` | unverified | unverified |
| `scikit-learn__scikit-learn-110` | unverified | unverified |
| `aio-libs__aiohttp-4100` | unverified | unverified |
| `sphinx-doc__sphinx-8714` | unverified | unverified |

## 5. Interpretation & Limitations

- **Benchmark is curated, not official SWE-bench**: The 20 instances in `evaluation/data/benchmark_set.json` are hand-selected real open-source bugs, but evaluated without the official per-repo Dockerized conda environments that SWE-bench requires. Results cannot be directly compared to published SWE-bench Lite scores.
- **Unverified means Docker sandbox unavailable**: Any `unverified` result means the Docker sandbox returned a timeout or daemon-unavailable error. The LLM patch may be correct but we cannot confirm it.
- **Confidence score is not a correctness guarantee**: It aggregates signal agreement (test results, static analysis, historical match, LLM consistency). Low scores flag uncertain patches; high scores still require human review before merging.
- **Rate limits caused backoff**: The Groq API returned 429s at high request density, handled via exponential backoff in `core/llm_caller.py`.
