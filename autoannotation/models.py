import os


# autoannotation/models.py

# Model roles are deliberately separated: summary models create independent
# section candidates, a consensus model reconciles each section, and an
# aggregation model synthesizes across papers. The consensus prompt expects
# exactly three summary candidates.
# === Performance models ===
PERF_MODELS = {
    'summary': ['mistral-nemo:12b','llama3:8b','gemma3:12b'],
    'consensus': 'phi4:14b',
    'aggregation': 'gemma3:12b'
}

# === Lite models (<3GB each) ===
# Use smaller, RAM-friendly alternatives that roughly mimic variety:
LITE_MODELS = {
    'summary': ['mistral:7b-instruct', 'llama3.2:3b', 'gemma3:4b'],
    'consensus': 'phi3:3.8b',
    'aggregation': 'gemma3:4b'
}

def _parse_summary_models(value):
    if not value:
        return None
    models = [item.strip() for item in value.split(',') if item.strip()]
    if len(models) != 3:
        raise ValueError('AUTOANNOTATION_SUMMARY_MODELS must contain exactly three models')
    return models


def _select_model_set(mode):
    normalized_mode = mode.strip().lower()
    if normalized_mode == 'performance':
        return PERF_MODELS
    if normalized_mode == 'lite':
        return LITE_MODELS
    raise ValueError("AUTOANNOTATION_MODEL_MODE must be 'performance' or 'lite'")


# === Select mode ===
MODE = os.getenv('AUTOANNOTATION_MODEL_MODE', 'performance')
MODEL_SET = _select_model_set(MODE)

MODEL_SUMMARY = (
    _parse_summary_models(os.getenv('AUTOANNOTATION_SUMMARY_MODELS'))
    or MODEL_SET['summary']
)
MODEL_CONSENSUS = os.getenv('AUTOANNOTATION_CONSENSUS_MODEL') or MODEL_SET['consensus']
MODEL_AGGREGATION = os.getenv('AUTOANNOTATION_AGGREGATION_MODEL') or MODEL_SET['aggregation']
# Regex generation reuses the reconciliation-strength model by default because
# it must produce a single, well-formed pattern rather than creative prose.
MODEL_REGEX = os.getenv('AUTOANNOTATION_REGEX_MODEL') or MODEL_CONSENSUS
