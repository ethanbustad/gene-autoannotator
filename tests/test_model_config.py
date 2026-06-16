import importlib

from autoannotation import models


def reload_models(monkeypatch, **env):
    for key in (
        "AUTOANNOTATION_MODEL_MODE",
        "AUTOANNOTATION_SUMMARY_MODELS",
        "AUTOANNOTATION_CONSENSUS_MODEL",
        "AUTOANNOTATION_AGGREGATION_MODEL",
        "AUTOANNOTATION_REGEX_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(models)


def test_model_config_defaults_to_performance_models(monkeypatch):
    configured = reload_models(monkeypatch)

    assert configured.MODEL_SUMMARY == [
        "mistral-nemo:12b",
        "llama3:8b",
        "gemma3:12b",
    ]
    assert configured.MODEL_CONSENSUS == "phi4:14b"
    assert configured.MODEL_AGGREGATION == "gemma3:12b"


def test_model_config_can_use_lite_mode(monkeypatch):
    configured = reload_models(monkeypatch, AUTOANNOTATION_MODEL_MODE="lite")

    assert configured.MODEL_SUMMARY == [
        "mistral:7b-instruct",
        "llama3.2:3b",
        "gemma3:4b",
    ]
    assert configured.MODEL_CONSENSUS == "phi3:3.8b"
    assert configured.MODEL_AGGREGATION == "gemma3:4b"


def test_model_config_can_be_overridden_by_environment(monkeypatch):
    configured = reload_models(
        monkeypatch,
        AUTOANNOTATION_SUMMARY_MODELS=(
            "mistral:7b-instruct-v0.2-q3_K_M,llama3.2:3b,gemma3:4b"
        ),
        AUTOANNOTATION_CONSENSUS_MODEL="phi3:3.8b",
        AUTOANNOTATION_AGGREGATION_MODEL="gemma3:4b",
    )

    assert configured.MODEL_SUMMARY == [
        "mistral:7b-instruct-v0.2-q3_K_M",
        "llama3.2:3b",
        "gemma3:4b",
    ]
    assert configured.MODEL_CONSENSUS == "phi3:3.8b"
    assert configured.MODEL_AGGREGATION == "gemma3:4b"


def test_regex_model_defaults_to_consensus_model(monkeypatch):
    configured = reload_models(monkeypatch)

    assert configured.MODEL_REGEX == "phi4:14b"


def test_regex_model_can_be_overridden(monkeypatch):
    configured = reload_models(monkeypatch, AUTOANNOTATION_REGEX_MODEL="qwen2.5:7b-instruct")

    assert configured.MODEL_REGEX == "qwen2.5:7b-instruct"
