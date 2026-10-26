import os
import json
import logging
from typing import List, Dict, Any, Optional
from datasets import load_dataset
from pathlib import Path

logger = logging.getLogger(__name__)

class DatasetLoader:
    def __init__(self, cache_dir: str = ".cache/swe_bench"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_name = "princeton-nlp/SWE-bench_Lite"
        
    def load_dataset(self, split: str = "test", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Loads the SWE-bench / curated benchmark dataset.
        Checks for local curated benchmark set first, then cache, then Hugging Face.
        """
        local_curated = Path(__file__).parent / "data" / "benchmark_set.json"
        cache_file = self.cache_dir / f"{split}_data.json"

        if local_curated.exists():
            logger.info(f"Loading curated benchmark dataset from {local_curated}")
            with open(local_curated, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif cache_file.exists():
            logger.info(f"Loading from local cache: {cache_file}")
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            logger.info("Fetching from Hugging Face...")
            dataset: Any = load_dataset(self.dataset_name, split=split)
            data = []
            for item in dataset:
                it: Any = item
                data.append({
                    "instance_id": it["instance_id"],
                    "repo": it["repo"],
                    "base_commit": it["base_commit"],
                    "problem_statement": it["problem_statement"],
                    "hints_text": it.get("hints_text", ""),
                    "created_at": it.get("created_at", ""),
                    "patch": it.get("patch", ""),
                    "test_patch": it.get("test_patch", ""),
                    "version": it.get("version", ""),
                    "fail_to_pass": it.get("fail_to_pass", []),
                    "pass_to_pass": it.get("pass_to_pass", []),
                    "environment_setup_commit": it.get("environment_setup_commit", "")
                })
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)

                
        if limit is not None:
            data = data[:limit]
            
        logger.info(f"Loaded {len(data)} instances.")
        return data
