#!/usr/bin/env python3
import asyncio
import argparse
import sys
import os

# Add parent directory of 'fixforge' to path to allow importing fixforge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fixforge.evaluation.metrics import MetricsTracker
from fixforge.evaluation.benchmark_runner import BenchmarkRunner
from fixforge.evaluation.baseline_runner import BaselineRunner
from fixforge.evaluation.ablation_study import AblationRunner

from rich.console import Console
from rich.panel import Panel

console = Console()

async def main():
    parser = argparse.ArgumentParser(description="FixForge AI Evaluation Harness")
    parser.add_argument("--limit", type=int, default=10, help="Number of SWE-bench instances to evaluate")
    parser.add_argument("--run-baseline", action="store_true", help="Run the single-shot LLM baseline")
    parser.add_argument("--run-benchmark", action="store_true", help="Run the full 7-agent FixForge LangGraph workflow")
    parser.add_argument("--run-ablation", action="store_true", help="Run the confidence score ablation study")
    parser.add_argument("--all", action="store_true", help="Run all evaluations")
    parser.add_argument("--output-dir", type=str, default="evaluation_results", help="Directory to save evaluation results")
    
    args = parser.parse_args()
    
    run_bl = args.run_baseline or args.all
    run_bm = args.run_benchmark or args.all
    run_ab = args.run_ablation or args.all
    
    if not any([run_bl, run_bm, run_ab]):
        console.print("[yellow]No execution flags provided. Defaulting to full benchmark run.[/yellow]")
        run_bm = True

    console.print(Panel.fit("FixForge AI Evaluation Harness", style="bold blue"))
    
    tracker = MetricsTracker()
    
    if run_bl:
        console.print("\n[bold green]=== Starting Baseline Evaluation ===[/bold green]")
        baseline = BaselineRunner(tracker)
        await baseline.run_baseline(limit=args.limit)
        
    if run_bm:
        console.print("\n[bold green]=== Starting Benchmark Evaluation ===[/bold green]")
        benchmark = BenchmarkRunner(tracker)
        await benchmark.run_benchmark(limit=args.limit)
        
    if run_ab:
        console.print("\n[bold green]=== Starting Ablation Study ===[/bold green]")
        ablation = AblationRunner(tracker)
        await ablation.run_ablation(limit=args.limit)
        
    console.print(f"\n[bold cyan]=== Compiling Results to {args.output_dir} ===[/bold cyan]")
    tracker.export(output_dir=args.output_dir)
    
    # Print summary to console
    summary = tracker.compute_metrics()
    console.print("\n[bold]Summary Metrics:[/bold]")
    for key, value in summary.items():
        if key == "comparison":
            console.print(f"\n[bold magenta]Delta (FixForge vs Baseline):[/bold magenta] {value['retry_loop_contribution_delta']:.2f}%")
        else:
            console.print(f"\n[bold]{key.capitalize()}:[/bold]")
            for m_key, m_val in value.items():
                if isinstance(m_val, float):
                    console.print(f"  {m_key}: {m_val:.2f}")
                else:
                    console.print(f"  {m_key}: {m_val}")

if __name__ == "__main__":
    asyncio.run(main())
