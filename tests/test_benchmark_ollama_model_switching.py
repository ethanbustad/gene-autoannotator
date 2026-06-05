import importlib.util
from pathlib import Path


def load_benchmark_module():
    path = Path(__file__).with_name("benchmark_ollama_model_switching.py")
    spec = importlib.util.spec_from_file_location("benchmark_ollama_model_switching", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_strategy_uses_direct_ollama_load_metrics():
    benchmark = load_benchmark_module()
    requests = [
        {
            "model_name": "model-a",
            "duration_sec": 10.0,
            "model_switched": False,
            "ollama_metrics": {
                "load_duration_sec": 2.0,
                "eval_duration_sec": 5.0,
                "prompt_eval_duration_sec": 1.0,
            },
        },
        {
            "model_name": "model-b",
            "duration_sec": 12.0,
            "model_switched": True,
            "ollama_metrics": {
                "load_duration_sec": 3.0,
                "eval_duration_sec": 6.0,
                "prompt_eval_duration_sec": 1.5,
            },
        },
    ]

    summary = benchmark.summarize_strategy(
        "depth_first",
        total_runtime_sec=22.0,
        requests=requests,
        transitions=[{"previous_model": "model-a", "new_model": "model-b"}],
        memory_samples=[],
    )

    assert summary["number_of_model_switches"] == 1
    assert summary["total_model_load_time_sec"] == 5.0
    assert summary["total_generation_time_sec"] == 11.0
    assert summary["total_prompt_eval_time_sec"] == 2.5
    assert summary["total_model_switch_overhead_sec"] == 3.0
    assert summary["switch_overhead_method"] == "ollama_load_duration_on_switches"


def test_summarize_strategy_estimates_switch_overhead_without_load_metrics():
    benchmark = load_benchmark_module()
    requests = [
        {
            "model_name": "model-a",
            "duration_sec": 8.0,
            "model_switched": False,
            "ollama_metrics": {},
        },
        {
            "model_name": "model-b",
            "duration_sec": 7.0,
            "model_switched": False,
            "ollama_metrics": {},
        },
        {
            "model_name": "model-b",
            "duration_sec": 13.0,
            "model_switched": True,
            "ollama_metrics": {},
        },
    ]

    summary = benchmark.summarize_strategy(
        "breadth_first",
        total_runtime_sec=28.0,
        requests=requests,
        transitions=[{"previous_model": "model-a", "new_model": "model-b"}],
        memory_samples=[],
    )

    assert summary["total_model_load_time_sec"] is None
    assert summary["total_generation_time_sec"] is None
    assert summary["total_model_switch_overhead_sec"] == 6.0
    assert summary["switch_overhead_method"] == "estimated_switch_request_excess"


def test_compute_improvement_reports_percent_reductions():
    benchmark = load_benchmark_module()

    improvement = benchmark.compute_improvement(
        {
            "total_runtime_sec": 100.0,
            "number_of_model_switches": 10,
            "total_model_switch_overhead_sec": 40.0,
        },
        {
            "total_runtime_sec": 75.0,
            "number_of_model_switches": 4,
            "total_model_switch_overhead_sec": 10.0,
        },
    )

    assert improvement["runtime_reduction_percent"] == 25.0
    assert improvement["model_switch_reduction_percent"] == 60.0
    assert improvement["model_switch_overhead_reduction_percent"] == 75.0
