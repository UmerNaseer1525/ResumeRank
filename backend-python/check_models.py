import joblib
import json
from pathlib import Path

print("=" * 70)
print("MODEL STATUS CHECK")
print("=" * 70)

# Check BERT
bert_meta = Path('app/models/resume_ranker_bert/metadata.json')
if bert_meta.exists():
    with open(bert_meta) as f:
        meta = json.load(f)
    metrics = meta.get('metrics', {})
    print("\n[BERT Model]")
    print(f"  Accuracy: {metrics.get('accuracy', 'N/A')}")
    print(f"  F1: {metrics.get('f1', 'N/A')}")
    print(f"  Precision: {metrics.get('precision', 'N/A')}")
    print(f"  Recall: {metrics.get('recall', 'N/A')}")
    print(f"  Samples: {metrics.get('sampleCount', 'N/A')}")
else:
    print("\n[BERT Model] NOT FOUND")

# Check Classical
classical_path = Path('app/models/resume_ranker.joblib')
if classical_path.exists():
    payload = joblib.load(classical_path)
    if isinstance(payload, dict):
        metrics = payload.get('metrics', {})
        print("\n[Classical Model]")
        print(f"  Accuracy: {metrics.get('accuracy', 'N/A')}")
        print(f"  F1: {metrics.get('f1', 'N/A')}")
        print(f"  Precision: {metrics.get('precision', 'N/A')}")
        print(f"  Recall: {metrics.get('recall', 'N/A')}")
        print(f"  Samples: {metrics.get('sampleCount', 'N/A')}")
else:
    print("\n[Classical Model] NOT FOUND")

# Check what get_model_status returns
print("\n" + "=" * 70)
print("API ENDPOINT RESPONSE")
print("=" * 70)

from app.services.ml_ranker import get_model_status
status = get_model_status()
print(f"\nAccuracy: {status.get('accuracy', 'N/A')}")
print(f"F1: {status.get('f1', 'N/A')}")
print(f"Model Kind: {status.get('modelKind', 'N/A')}")
print(f"Score Source: {status.get('scoreSource', 'N/A')}")
