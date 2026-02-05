import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app.services.llm import LLMService

# Test LLM directly
llm = LLMService()

print("=" * 60)
print("LLM SERVICE TEST")
print("=" * 60)
print(f"API Key configured: {llm.api_key is not None}")
print(f"Base URL: {llm.base_url}")
print(f"Model: {llm.model}")
print(f"Client initialized: {llm.client is not None}")
print("=" * 60)

if llm.client:
    print("\n✅ LLM is configured and ready!")
    print("\nTesting with sample evidence...")
    
    test_evidence = {
        "metadata": {
            "confidence_score": 0.80,
            "max_phase": 4,
            "deduplicated_evidence_count": 5,
            "unique_sources": 3,
            "evidence_types": ["Known Drug Database"],
            "reasoning": "Clinically approved drug-target interaction"
        },
        "evidence_items": [
            {
                "drug": "ASPIRIN",
                "target": "PTGS1",
                "mechanism": "Cyclooxygenase inhibitor",
                "phase": 4,
                "drugType": "Small molecule",
                "references": []
            }
        ]
    }
    
    explanation = llm.analyze(test_evidence)
    print("\n📝 LLM Generated Explanation:")
    print("-" * 60)
    print(explanation)
    print("-" * 60)
else:
    print("\n❌ LLM client not initialized - check your API key")
