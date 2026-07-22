# autoannotation/models.py

PERF_MODELS = {
    'summary': ['mistral-nemo:12b','qwen3.5:9b','gemma4:12b'],
    'consensus': 'phi4:14b',
    'aggregation': 'gemma4:12b'
}

# Use smaller, RAM-friendly alternatives that roughly mimic variety:
LITE_MODELS = {
    'summary': ['granite4.1:3b', 'qwen3.5:4b', 'gemma4:e4b'],
    'consensus': 'ministral-3:3b',
    'aggregation': 'gemma4:e4b'
}

MODE = 'performance'   # 'performance' or 'lite'

if MODE == 'performance':
    MODEL_SUMMARY = PERF_MODELS['summary']
    MODEL_CONSENSUS = PERF_MODELS['consensus']
    MODEL_AGGREGATION = PERF_MODELS['aggregation']
else:
    MODEL_SUMMARY = LITE_MODELS['summary']
    MODEL_CONSENSUS = LITE_MODELS['consensus']
    MODEL_AGGREGATION = LITE_MODELS['aggregation']