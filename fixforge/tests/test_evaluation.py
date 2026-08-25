import pytest
import asyncio
from fixforge.evaluation.metrics import MetricsTracker
from fixforge.evaluation.dataset_loader import DatasetLoader
from fixforge.evaluation.benchmark_runner import BenchmarkRunner
from fixforge.evaluation.baseline_runner import BaselineRunner
from fixforge.evaluation.ablation_study import AblationRunner

def test_metrics_tracker_frr():
    tracker = MetricsTracker()
    tracker.record_result("fixforge", {"resolved": True, "latency_seconds": 10})
    tracker.record_result("fixforge", {"resolved": False, "latency_seconds": 20})
    
    summary = tracker.compute_metrics()
    assert summary["fixforge"]["fix_resolution_rate"] == 50.0
    assert summary["fixforge"]["mean_time_to_fix"] == 15.0

def test_metrics_tracker_delta():
    tracker = MetricsTracker()
    tracker.record_result("fixforge", {"resolved": True, "latency_seconds": 10})
    tracker.record_result("baseline", {"resolved": False, "latency_seconds": 10})
    
    summary = tracker.compute_metrics()
    assert summary["comparison"]["retry_loop_contribution_delta"] == 100.0

@pytest.mark.asyncio
async def test_benchmark_runner_initialization():
    tracker = MetricsTracker()
    runner = BenchmarkRunner(tracker)
    assert runner.metrics_tracker == tracker

@pytest.mark.asyncio
async def test_baseline_runner_initialization():
    tracker = MetricsTracker()
    runner = BaselineRunner(tracker)
    assert runner.metrics_tracker == tracker

def test_dataset_loader_initialization():
    loader = DatasetLoader(cache_dir="/tmp/test_cache")
    assert loader.dataset_name == "princeton-nlp/SWE-bench_Lite"
