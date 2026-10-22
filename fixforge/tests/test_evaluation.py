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


def test_unverified_cannot_count_as_resolved():
    """
    Stage 3 Gate Requirement:
    Prove that if Docker sandbox status is 'unverified', the run CANNOT count as resolved,
    even if an upstream heuristic or simulated test claims test_passed=True.
    """
    tracker = MetricsTracker()
    tracker.record_result("fixforge", {
        "docker_status": "unverified",
        "test_passed": True,
        "agent_sources": ["llm", "llm", "llm"],
        "resolved": True  # Attempt to pass raw True
    })
    summary = tracker.compute_metrics()
    assert summary["fixforge"]["resolved"] == 0, "Unverified run must never count as resolved!"
    assert summary["fixforge"]["resolution_rate"] == 0.0
    assert summary["fixforge"]["unverified"] == 1


def test_fallback_cannot_count_as_resolved():
    """
    Stage 3 Gate Requirement:
    Prove that if any agent used fallback heuristics ('fallback'), the run CANNOT count as resolved,
    even if Docker tests passed.
    """
    tracker = MetricsTracker()
    tracker.record_result("fixforge", {
        "docker_status": "passed",
        "test_passed": True,
        "agent_sources": ["llm", "fallback", "llm"],
        "resolved": True  # Attempt to pass raw True
    })
    summary = tracker.compute_metrics()
    assert summary["fixforge"]["resolved"] == 0, "Fallback run must never count as resolved!"
    assert summary["fixforge"]["resolution_rate"] == 0.0
    assert summary["fixforge"]["fallback"] == 1


def test_patch_failed_cannot_count_as_resolved():
    """
    Stage 3 Gate Requirement:
    Prove that if candidate patch was rejected by git apply ('patch_failed'),
    it cannot count as resolved.
    """
    tracker = MetricsTracker()
    tracker.record_result("fixforge", {
        "docker_status": "patch_failed",
        "test_passed": False,
        "agent_sources": ["llm", "llm", "llm"],
        "resolved": False
    })
    summary = tracker.compute_metrics()
    assert summary["fixforge"]["resolved"] == 0
    assert summary["fixforge"]["patch_failed"] == 1


def test_only_live_llm_and_docker_passed_counts_as_resolved():
    """
    Stage 3 Gate Requirement:
    Only when Docker status is 'passed', tests pass, AND all agents are 'llm'
    does the instance legitimately count as resolved.
    """
    tracker = MetricsTracker()
    tracker.record_result("fixforge", {
        "docker_status": "passed",
        "test_passed": True,
        "agent_sources": ["llm", "llm", "llm"]
    })
    summary = tracker.compute_metrics()
    assert summary["fixforge"]["resolved"] == 1
    assert summary["fixforge"]["resolution_rate"] == 100.0
    assert summary["fixforge"]["unverified"] == 0
    assert summary["fixforge"]["fallback"] == 0

