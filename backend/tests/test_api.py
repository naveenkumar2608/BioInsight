import requests
import json

# Test the API with Erlotinib -> EGFR
url = "http://127.0.0.1:8000/api/analyze"
payload = {
    "drug": "Erlotinib",
    "target": "EGFR"
}

response = requests.post(url, json=payload)
result = response.json()

print("=" * 60)
print("ERLOTINIB → EGFR TEST")
print("=" * 60)
print(f"\nConfidence Score: {result['confidence_score']}")
print(f"Evidence Count: {result['raw_evidence_count']}")
print(f"Sources: {', '.join(result['evidence_sources'])}")
print(f"\nExplanation:\n{result['explanation']}")
print("=" * 60)
