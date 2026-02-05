import asyncio
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.llm import LLMService

async def test_extraction():
    llm = LLMService()
    
    queries = [
        "How does Losartan interact with AGTR1 mechanistically?",
        "Tell me about the interaction between Integrin beta-6 and gefitinib",
        "Does α-synuclein relate to bcr abl?",
        "How does vergfr2 interact with vegf-r2?"
    ]
    
    print("=" * 60)
    print("LLM EXTRACTION PIPELINE TEST")
    print("=" * 60)
    
    for q in queries:
        print(f"\nQUERY: {q}")
        drug, target = await llm.extract_entities(q)
        print(f"FINAL RESULT -> Drug: {drug}, Target: {target}")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(test_extraction())
