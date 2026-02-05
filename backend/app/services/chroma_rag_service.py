import chromadb
import os
from typing import Dict, Optional, Tuple


class ChromaRAGService:
    def __init__(self, persist_directory: str = None):
        """
        Initialize ChromaDB with persistent storage.
        """
        if persist_directory is None:
            base_dir = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.abspath(__file__))
                    )
                )
            )
            persist_directory = os.path.join(
                base_dir, "Chatbot_data", "chroma_db"
            )

        print(f"Initializing ChromaRAGService with directory: {persist_directory}")

        # Disable telemetry BEFORE initializing client
        os.environ["CHROMA_TELEMETRY_ENABLED"] = "FALSE"
        from chromadb.config import Settings
        
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                is_persistent=True
            )
        )

        # ✅ SAFE COLLECTION INITIALIZATION
        self.drugs_collection = self.client.get_or_create_collection(
            name="drugs",
            metadata={"domain": "biomedical", "type": "drug"}
        )

        self.targets_collection = self.client.get_or_create_collection(
            name="targets",
            metadata={"domain": "biomedical", "type": "target"}
        )

        # Ensure essential clinical entities are present
        self._ensure_baseline_data()

    def _ensure_baseline_data(self):
        """
        Ensures essential clinical entities for testing are present in the vectors.
        Uses upsert to avoid duplicates and ensure they're always there.
        """
        # Drug baseline
        print("Ensuring baseline drug data...")
        self.drugs_collection.upsert(
            documents=[
                "Imatinib", "Aspirin", "Erlotinib", "Gefitinib", 
                "Trastuzumab", "Fluoxetine", "Metformin", "Paracetamol",
                "Atorvastatin"
            ],
            ids=[
                "seed_imatinib", "seed_aspirin", "seed_erlotinib", "seed_gefitinib", 
                "seed_trastuzumab", "seed_fluoxetine", "seed_metformin", "seed_paracetamol",
                "seed_atorvastatin"
            ]
        )

        # Target baseline
        print("Ensuring baseline target data...")
        self.targets_collection.upsert(
            documents=[
                "BCR-ABL1", "PTGS1 (COX-1)", "PTGS2 (COX-2)", "EGFR", 
                "ERBB2 (HER2)", "SLC6A4 (Serotonin Transporter)", "PPARG",
                "PRKAA1 (AMPK)", "HMGCR"
            ],
            ids=[
                "seed_bcr_abl1", "seed_ptgs1", "seed_ptgs2", "seed_egfr", 
                "seed_her2", "seed_serotonin", "seed_pparg", "seed_ampk",
                "seed_hmgcr"
            ]
        )

    def find_best_matches(self, drug_query: str, target_query: str) -> Tuple[Optional[str], Optional[str], float]:
        """
        Validate and find best matching formal names for extracted drug and target.
        Returns (drug_name, target_name, confidence).
        """
        final_drug = None
        final_target = None
        drug_dist = 2.0
        target_dist = 2.0

        # Validate Drug
        if drug_query:
            res = self.drugs_collection.query(query_texts=[drug_query], n_results=1)
            if res.get("distances") and res["distances"][0]:
                dist = res["distances"][0][0]
                doc = res["documents"][0][0]
                if dist < 0.8 or (drug_query.lower() in doc.lower() and dist < 1.2):
                    final_drug = doc
                    drug_dist = dist

        # Validate Target
        if target_query:
            res = self.targets_collection.query(query_texts=[target_query], n_results=1)
            if res.get("distances") and res["distances"][0]:
                dist = res["distances"][0][0]
                doc = res["documents"][0][0]
                if dist < 0.8 or (target_query.lower() in doc.lower() and dist < 1.2):
                    # Clean symbol if needed
                    final_target = doc.split(" (")[0] if "(" in doc else doc
                    target_dist = dist

        # Calculate Confidence
        # Max distance 1.2 -> Confidence 0.0, Distance 0.0 -> Confidence 1.0
        d_conf = max(0, (1.2 - drug_dist) / 1.2) if final_drug else 0
        t_conf = max(0, (1.2 - target_dist) / 1.2) if final_target else 0
        
        overall_confidence = (d_conf + t_conf) / 2 if (final_drug and final_target) else 0
        
        return final_drug, final_target, overall_confidence

    def search_candidates(self, query_text: str) -> Dict[str, Optional[str]]:
        """
        Full-sentence RAG extraction as a fallback for when regex fails.
        """
        from app.utils.extraction import get_candidates
        candidates = get_candidates(query_text)
        
        if not candidates:
            return {"drug": None, "target": None}

        # Similar logic to previous find_best_matches but returning Dict
        final_drug = None
        final_target = None
        best_d = 0.4  # Strict threshold (was 1.0)
        best_t = 0.4  # Strict threshold (was 1.0)

        d_res = self.drugs_collection.query(query_texts=candidates, n_results=1)
        t_res = self.targets_collection.query(query_texts=candidates, n_results=1)

        for i, dists in enumerate(d_res["distances"]):
            if dists and dists[0] < best_d:
                best_d = dists[0]
                final_drug = d_res["documents"][i][0]

        for i, dists in enumerate(t_res["distances"]):
            if dists and dists[0] < best_t:
                best_t = dists[0]
                doc = t_res["documents"][i][0]
                final_target = doc.split(" (")[0] if "(" in doc else doc

        return {"drug": final_drug, "target": final_target}


# ------------------- LOCAL TEST -------------------
if __name__ == "__main__":
    service = ChromaRAGService()

    test_queries = [
        "How does Imatinib interact with BCR-ABL1?",
        "Tell me about Aspirin and PTGS1",
        "Erlotinib and EGFR interaction",
        "What does Gefitinib target?",
        "Explain Paracetamol mechanism",
        "Is Trastuzumab associated with HER2"
    ]

    print("\n" + "=" * 60)
    print("CHROMA RAG ENTITY EXTRACTION TEST")
    print("=" * 60)

    for query in test_queries:
        result = service.find_best_matches(query)
        print(f"\nQuery: {query}")
        print(f"Extracted Drug  : {result['drug']}")
        print(f"Extracted Target: {result['target']}")

    print("\n" + "=" * 60)
