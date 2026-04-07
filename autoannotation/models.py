# autoannotation/models.py

# === Performance models ===
PERF_MODELS = {
    'summary': ['mistral-nemo:12b','llama3:8b','gemma3:12b'],
    'consensus': 'phi4:14b',
    'aggregation': 'gemma3:12b'
}

# === Lite models (<3GB each) ===
# Use smaller, RAM-friendly alternatives that roughly mimic variety:
# - Replace Mistral, LLaMA3, Gemma3 with smaller llama2/mistral models
# - Keep one “fast reasoning” and one “general purpose” model
LITE_MODELS = {
    'summary': ['mistral-mini:2b', 'llama2-3b', 'gemma-mini:2b'],
    'consensus': 'phi-mini:2b',
    'aggregation': 'gemma-mini:2b'
}

# === Select mode ===
MODE = 'performance'   # 'performance' or 'lite'

if MODE == 'performance':
    MODEL_SUMMARY = PERF_MODELS['summary']
    MODEL_CONSENSUS = PERF_MODELS['consensus']
    MODEL_AGGREGATION = PERF_MODELS['aggregation']
else:
    MODEL_SUMMARY = LITE_MODELS['summary']
    MODEL_CONSENSUS = LITE_MODELS['consensus']
    MODEL_AGGREGATION = LITE_MODELS['aggregation']