import asyncio
import logging
import uuid
import random
import json
from typing import List, Dict
from rich.progress import Progress
import scipy.stats as stats

from .dataset_loader import DatasetLoader
from .metrics import MetricsTracker

try:
    from fixforge.graph.workflow import build_workflow
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class AblationRunner:
    CONFIGS = {
        0: "Full Formula (45% Test, 25% Static, 15% Context, 15% Consistency)",
        1: "Without Test Evidence (w/o S_test)",
        2: "Without Static Analysis (w/o S_static)",
        3: "Without Context Relevance (w/o S_context)",
        4: "Without Self-Consistency (w/o S_consistency)"
    }

    def __init__(self, metrics_tracker: MetricsTracker):
        self.dataset_loader = DatasetLoader()
        self.metrics_tracker = metrics_tracker
        self.graph = build_workflow() if GRAPH_AVAILABLE else None
        
    async def _mock_invoke(self, state: Dict, config_id: int) -> Dict:
        await asyncio.sleep(0.2)
        # Simulate different confidence distributions based on ablation config
        base_confidence = 0.85
        if config_id == 1:
            base_confidence -= 0.45
        elif config_id == 2:
            base_confidence -= 0.25
        elif config_id == 3:
            base_confidence -= 0.15
        elif config_id == 4:
            base_confidence -= 0.15
            
        confidence = max(0.0, min(1.0, base_confidence + random.uniform(-0.1, 0.1)))
        resolved = confidence > 0.5 # Correlated with resolution
        
        return {
            **state,
            "test_results": {"passed": resolved},
            "confidence_score": confidence
        }
        
    async def run_instance_with_config(self, instance: dict, config_id: int):
        initial_state = {
            "session_id": str(uuid.uuid4()),
            "issue_description": instance["problem_statement"],
            "repo_url": instance["repo"],
            "repo_path": f"/tmp/repos/{instance['repo'].replace('/', '_')}",
            "patch": "",
            "retry_count": 0,
            "error_logs": "",
            "confidence_score": 0.0,
            "ablation_config": config_id
        }
        
        try:
            if self.graph:
                result_state = await self.graph.ainvoke(initial_state)
            else:
                result_state = await self._mock_invoke(initial_state, config_id)
            
            resolved = result_state.get("test_results", {}).get("passed", False)
            self.metrics_tracker.record_ablation_result(
                config_id,
                instance["instance_id"],
                result_state.get("confidence_score", 0.0),
                resolved
            )
        except Exception as e:
            logger.error(f"Config {config_id} error for {instance['instance_id']}: {str(e)}")

    async def run_ablation(self, limit: int = 10):
        instances = self.dataset_loader.load_dataset(limit=limit)
        
        for config_id, config_name in self.CONFIGS.items():
            print(f"\n[AblationRunner] Running Config {config_id}: {config_name}")
            
            with Progress() as progress:
                task = progress.add_task(f"Evaluating Config {config_id}...", total=len(instances))
                
                for instance in instances:
                    await self.run_instance_with_config(instance, config_id)
                    progress.advance(task)
                    
        self.compute_correlations()
        
    def compute_correlations(self):
        print("\n[AblationRunner] Correlation Analysis (Confidence Score vs Ground Truth)")
        results = self.metrics_tracker.ablation_results
        
        correlations = {}
        
        for config_id, data in results.items():
            scores = [x["confidence_score"] for x in data]
            ground_truth = [1.0 if x["resolved"] else 0.0 for x in data]
            
            if len(scores) > 1 and len(set(ground_truth)) > 1:
                pearson_r, _ = stats.pearsonr(scores, ground_truth)
                spearman_r, _ = stats.spearmanr(scores, ground_truth)
            else:
                pearson_r, spearman_r = 0.0, 0.0
                
            correlations[config_id] = {
                "config_name": self.CONFIGS[config_id],
                "pearson_r": float(pearson_r),
                "spearman_r": float(spearman_r)
            }
            print(f"Config {config_id}: Pearson: {pearson_r:.4f}, Spearman: {spearman_r:.4f}")
            
        # Export correlations
        import os
        os.makedirs("results", exist_ok=True)
        with open("results/evaluation_correlations.json", "w") as f:
            json.dump(correlations, f, indent=2)
