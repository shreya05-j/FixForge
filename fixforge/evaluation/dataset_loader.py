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
        Loads the SWE-bench Lite dataset from Hugging Face.
        Caches the metadata locally.
        """
        logger.info(f"Loading {self.dataset_name} ({split} split)...")
        cache_file = self.cache_dir / f"{split}_data.json"
        
        if cache_file.exists():
            logger.info(f"Loading from local cache: {cache_file}")
            with open(cache_file, "r") as f:
                data = json.load(f)
        else:
            logger.info("Fetching from Hugging Face...")
            dataset = load_dataset(self.dataset_name, split=split)
            data = [
                {
                    "instance_id": item["instance_id"],
                    "repo": item["repo"],
                    "base_commit": item["base_commit"],
                    "problem_statement": item["problem_statement"],
                    "hints_text": item.get("hints_text", ""),
                    "created_at": item.get("created_at", ""),
                    "patch": item.get("patch", ""),
                    "test_patch": item.get("test_patch", ""),
                    "version": item.get("version", ""),
                    "fail_to_pass": item.get("fail_to_pass", []),
                    "pass_to_pass": item.get("pass_to_pass", []),
                    "environment_setup_commit": item.get("environment_setup_commit", "")
                }
                for item in dataset
            ]
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
                
        if limit is not None:
            data = data[:limit]
            
        logger.info(f"Loaded {len(data)} instances.")
        return data
