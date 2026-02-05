"""
Updated LLM Service with RAG-based Entity Extraction
This replaces the Gemini API dependency for entity extraction
"""

import os
import json
import re
import requests
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dotenv import load_dotenv

# Import RAG services
from app.services.chroma_rag_service import ChromaRAGService
from app.services.opentargets import search_target_id, search_drug_id

load_dotenv()

SYSTEM_PROMPT = """You are a strict biomedical data reporter. Your only job is to describe the JSON evidence provided. 

STRICT RULES:
1. NO EXTERNAL KNOWLEDGE: If it is not in the JSON, it doesn't exist. Do not use your own training data about drugs.
2. ZERO CONFIDENCE RULE: If the confidence_score in metadata is 0.0, you MUST state "No evidence found" and explain that no clinical or preclinical data was retrieved. DO NOT guess a mechanism.
3. NO INFERENCE: Do not mention "safety profiles", "long-term effects", or "future trials" unless the word is in the evidence.
4. PHASE ACCURACY: Only mention a clinical phase if 'max_phase' is explicitly greater than 0. Otherwise, state the phase is undefined.
5. SOURCE CONSISTENCY: Only mention "consistency" if unique_sources is greater than 1.
"""

REASONING_PROMPT_TEMPLATE = """Analyze this interaction using ONLY the JSON below:
{STRUCTURED_EVIDENCE_JSON}

Rules:
- If evidence_count is 0, stop and report "No Data".
- List only the formal sources mentioned in 'evidence_sources'.
- State the mechanism from 'mechanismOfAction' exactly as written. If null, state "Mechanism undefined".
"""

EXPLANATION_PROMPT_TEMPLATE = """Based on the previous analysis:
{REASONING_OUTPUT}

Generate a 1-2 paragraph summary.
- If confidence is 0.0, skip drug descriptions and state: "This interaction is not supported by retrieved evidence."
- Do NOT speculate on safety or quality.
- Do NOT use generic phrases like "strong clinical evidence" if the score is low.
"""

FALLBACK_PROMPT = "The system could not retrieve valid evidence for this drug-target interaction. No clinical or preclinical data is available in the current search scope."


ENTITY_EXTRACTION_PROMPT = """You are a biomedical entity extractor. Extract the main drug and biological target (protein, gene, or receptor) from the user's query.

CRITICAL RULES:
- Return ONLY a JSON object.
- Keys: "drug", "target"
- Values: The name of the entity, or null if not found.
- If multiple are mentioned, pick the most prominent one.
- For targets, use the formal name or symbol (e.g., "HER2" or "ERBB2").

Query: {QUERY}

JSON Output:"""




class LLMService:
    """
    LLM Service with Hybrid AI: 
    - Ollama (DeepSeek) for Narrative Analysis
    - Ollama (DeepSeek) for Entity Extraction Fallback
    """
    
    def __init__(self):
        # 1. Ollama Configuration
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.model_name = os.getenv("LLM_MODEL", "deepseek-r1:1.5b")
        self.ollama_ready = False
        
        # Ollama status will be checked on first use
        self.ollama_ready = True 
        print(f"LLMService configured for model: {self.model_name}")

        # 3. Initialize ChromaDB-based search
        print("Initializing ChromaRAGService...")
        try:
            self.chroma_rag = ChromaRAGService()
            print("ChromaRAGService initialized.")
        except Exception as e:
            print(f"Warning: Failed to initialize ChromaRAGService: {e}")
            self.chroma_rag = None
        
            
    def analyze(self, evidence_data):
        """Generate explanation STRICTLY using Ollama DeepSeek"""
        # Hard constraint: Never ask LLM to explain 0% confidence
        metadata = evidence_data.get("metadata", {})
        if metadata.get("confidence_score") == 0.0 or not evidence_data.get("evidence_items"):
            return FALLBACK_PROMPT

        if self.ollama_ready:
            return self._analyze_with_ollama(evidence_data)
        else:
            return "Error: Local AI Assistant (Ollama DeepSeek) is not running. Please start Ollama to see the AI analysis."

    def _analyze_with_ollama(self, evidence_data):
        """Ollama/DeepSeek based analysis"""
        try:
            # 1. Prepare Data
            evidence_json = json.dumps(evidence_data, indent=2)

            # 2. Unified Prompt
            unified_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"Data to summarize:\n{evidence_json}\n\n"
                "TASK: Provide a factual summary based ONLY on the data above. "
                "Use scientific terminology appropriate for research. "
                "Ensure you mention the confidence score and the number of sources."
            )
            
            # 3. Call Local LLM
            raw_output = self._call_llm(unified_prompt)
            
            # 4. Clean thinking blocks and whitespace
            clean_output = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL).strip()
            
            return clean_output
        except Exception as e:
            print(f"Ollama DeepSeek Analysis Error: {str(e)}")
            return "Error: Failed to generate explanation using the local DeepSeek model. Ensure Ollama is healthy and the model is loaded."
    
    

    def _call_llm(self, prompt):
        """Call Local Ollama API"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3
                }
            }
            response = requests.post(self.ollama_url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            print(f"Ollama Call Error: {e}")
            raise e

    def _extract_with_llm(self, query: str) -> dict:
        """
        Step 4: LLM Fallback extraction (Ollama/DeepSeek)
        """
        if not self.ollama_ready:
            return {}
            
        prompt = ENTITY_EXTRACTION_PROMPT.replace("{QUERY}", query)
        try:
            raw_text = self._call_llm(prompt)
            
            # Clean thinking blocks for DeepSeek
            clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
            
            # Try to find JSON in the response (using a more robust approach)
            start = clean_text.find('{')
            end = clean_text.rfind('}')
            if start != -1 and end != -1:
                try:
                    return json.loads(clean_text[start:end+1])
                except json.JSONDecodeError:
                    # Fallback to regex if simple substring fails
                    json_match = re.search(r'(\{.*\})', clean_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(1))
            return {}
        except Exception as e:
            print(f"Ollama Extraction Error: {e}")
            return {}

    async def extract_entities(self, user_query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        IMPROVED 3-Step Extraction Pipeline:
        1. RAG/Dictionary
        2. Smart API candidate search (multi-word aware)
        3. LLM fallback (Ollama/DeepSeek) + API verification
        """
        from app.utils.extraction import normalize_text, generate_smart_candidates
        from app.services.opentargets import search_target_id, search_drug_id
        
        print("\n" + "─"*50)
        print("EXTRACTION PIPELINE START")
        print(f"Query: \"{user_query}\"")
        
        local_drug = None
        local_target = None
        
        # Normalize
        normalized_query = normalize_text(user_query)
        
        # Step 1: RAG/Dictionary
        print("   [Step 1] RAG Dictionary Search...", end=" ", flush=True)
        if self.chroma_rag:
            rag_entities = self.chroma_rag.search_candidates(normalized_query)
            local_drug = rag_entities.get("drug")
            local_target = rag_entities.get("target")
            
            if local_drug and local_target:
                print(f"SUCCESS → Drug: {local_drug}, Target: {local_target}")
                return local_drug, local_target
            print("INCOMPLETE")
        else:
            print("SKIPPED (Service Unavailable)")

        # Step 2: Smart API Candidate Search (Multi-word aware)
        if not local_drug or not local_target:
            print("   [Step 2] API Candidate Search (Open Targets)...")
            
            # Generate smart candidates (prioritizes multi-word entities)
            candidates = generate_smart_candidates(user_query)
            
            print(f"           Generated {len(candidates)} candidates")
            print(f"           Top 5: {candidates[:5]}")
            
            # === SEARCH FOR DRUG ===
            if not local_drug:
                print(f"           - Searching Drug...")
                for search_term in candidates:
                    print(f"             Trying: '{search_term}'...", end=" ", flush=True)
                    _, d_name = await search_drug_id(search_term)
                    if d_name:
                        local_drug = d_name
                        print(f"✓ FOUND ({local_drug})")
                        break
                    print("✗")
            
            # === SEARCH FOR TARGET ===
            if not local_target:
                print(f"           - Searching Target...")
                for search_term in candidates:
                    # Skip if it's the same as the drug we already found
                    if local_drug and search_term.lower() == local_drug.lower():
                        continue
                    
                    print(f"             Trying: '{search_term}'...", end=" ", flush=True)
                    _, t_name = await search_target_id(search_term)
                    if t_name:
                        local_target = t_name
                        print(f"✓ FOUND ({local_target})")
                        break
                    print("✗")
            
            if local_drug and local_target:
                print(f"   ✓ RESULT: Step 2 Success → Drug: {local_drug}, Target: {local_target}")
                return local_drug, local_target
            
            print(f"   ⚠ RESULT: Step 2 Partial → Drug: {local_drug or 'None'}, Target: {local_target or 'None'}")

        # Step 3: LLM fallback (Ollama/DeepSeek) + API Verification
        if not local_drug or not local_target:
            print(f"   [Step 3] LLM Fallback (Ollama/DeepSeek)...", end=" ", flush=True)
            from fastapi.concurrency import run_in_threadpool
            llm_entities = await run_in_threadpool(self._extract_with_llm, user_query)
            
            if llm_entities:
                print(f"LLM SUGGESTED: {llm_entities}")
                if not local_drug and llm_entities.get("drug"):
                    print(f"           - Verifying LLM drug '{llm_entities['drug']}' with API...", end=" ", flush=True)
                    _, d_name = await search_drug_id(llm_entities["drug"])
                    if d_name:
                        local_drug = d_name
                        print(f"SUCCESS ({d_name})")
                    else:
                        print("NOT FOUND")

                if not local_target and llm_entities.get("target"):
                    print(f"           - Verifying LLM target '{llm_entities['target']}' with API...", end=" ", flush=True)
                    _, t_name = await search_target_id(llm_entities["target"])
                    if t_name:
                        local_target = t_name
                        print(f"SUCCESS ({t_name})")
                    else:
                        print("NOT FOUND")
            else:
                print("FAILED (No response from AI or parsing error)")
        else:
            print("   [Step 3] LLM Fallback SKIPPED (Both entities already found)")

        # Final Evaluation
        if local_drug and local_target:
             print(f"   PIPELINE RESULT: SUCCESS ({local_drug} → {local_target})")
             print("─"*50 + "\n")
        else:
             print("   PIPELINE RESULT: EXTRACTION INCOMPLETE")
             print("─"*50 + "\n")
             
        return local_drug, local_target