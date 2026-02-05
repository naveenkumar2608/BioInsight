import requests
import json

def test_drug_target(drug, target):
    url = "http://127.0.0.1:8000/api/analyze"
    payload = {"drug": drug, "target": target}
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    print("=" * 70)
    print(f"{drug.upper()} → {target.upper()}")
    print("=" * 70)
    print(f"Confidence Score: {result['confidence_score']}")
    print(f"Evidence Count: {result['raw_evidence_count']}")
    print(f"Sources: {', '.join(result['evidence_sources']) if result['evidence_sources'] else 'None'}")
    print(f"\nExplanation:\n{result['explanation']}")
    print("=" * 70)
    print()

# Test all three examples
print("\n🧪 TESTING DRUG-TARGET ANALYSIS SYSTEM\n")

test_drug_target("Aspirin", "COX-1")
test_drug_target("Erlotinib", "EGFR")
test_drug_target("Fluoxetine", "Serotonin transporter")

print("✅ All tests completed!")
