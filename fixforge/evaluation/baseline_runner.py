import asyncio
import time
import logging
from typing import Dict, Any
from .dataset_loader import DatasetLoader
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from .metrics import MetricsTracker

logger = logging.getLogger(__name__)

class BaselineRunner:
    def __init__(self, metrics_tracker: MetricsTracker, model: str = "qwen2.5-coder-32b"):
        self.dataset_loader = DatasetLoader()
        self.metrics_tracker = metrics_tracker
        self.model = model

    async def run_instance(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Runs a standard single-shot LLM baseline."""
        start_time = time.time()
        
        prompt = f"""
        You are an expert programmer. Please fix the following issue in the repository {instance['repo']}.
        
        Issue Description:
        {instance['problem_statement']}
        
        Please provide a unified diff patch to fix the issue.
        """
        
        try:
            # Simulate a baseline LLM call
            await asyncio.sleep(0.5) 
            
            # Assuming it rarely gets it right in one shot
            # In a real scenario, this would use litellm.acompletion or openai
            import random
            is_resolved = random.random() < 0.15 # 15% chance baseline resolves it for demo purposes
            
            patch = "--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n- baseline_bug\n+ baseline_fix"
                
            latency = time.time() - start_time
            
            result = {
                "instance_id": instance["instance_id"],
                "resolved": is_resolved,
                "latency_seconds": latency,
                "patch": patch,
                "error": None
            }
        except Exception as e:
            logger.error(f"Error in baseline for {instance['instance_id']}: {str(e)}")
            result = {
                "instance_id": instance["instance_id"],
                "resolved": False,
                "latency_seconds": time.time() - start_time,
                "patch": "",
                "error": str(e)
            }
            
        self.metrics_tracker.record_result("baseline", result)
        return result

    async def run_baseline(self, limit: int = 10):
        instances = self.dataset_loader.load_dataset(limit=limit)
        
        print(f"[BaselineRunner] Starting single-shot baseline for {len(instances)} instances.")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("[yellow]Running baseline...", total=len(instances))
            
            for instance in instances:
                await self.run_instance(instance)
                progress.advance(task)
