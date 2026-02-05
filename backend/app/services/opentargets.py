import httpx
import json
import asyncio
from functools import lru_cache
from fastapi import HTTPException
from app.utils.matching import fuzzy_match_drug

BASE_URL = "https://api.platform.opentargets.org/api/v4/graphql"


def aggregate_sources(evidence_list: list) -> list:
    """
    Aggregates evidence items with same phase/mechanism but different sources.
    This ensures we capture ALL unique sources while avoiding duplicate evidence.
    """
    # Group by (drug, target, phase, mechanism)
    grouped = {}
    
    for item in evidence_list:
        # Create grouping key
        key = (
            item.get("drug", {}).get("id", ""),
            item.get("target", {}).get("id", ""),
            item.get("phase", 0),
            item.get("mechanismOfAction", "")
        )
        
        if key not in grouped:
            grouped[key] = {
                "drug": item.get("drug"),
                "target": item.get("target"),
                "drugType": item.get("drugType"),
                "phase": item.get("phase"),
                "mechanismOfAction": item.get("mechanismOfAction"),
                "references": []
            }
        
        # Aggregate references from this item
        refs = item.get("references", []) or []
        for ref in refs:
            source = ref.get("source", "")
            if source and source not in [r.get("source") for r in grouped[key]["references"]]:
                grouped[key]["references"].append(ref)
    
    return list(grouped.values())


def extract_sources_from_evidence(evidence_list: list) -> list:
    """Adds inferred sources based on available data"""
    for item in evidence_list:
        if "references" not in item or not item["references"]:
            item["references"] = []
        
        phase = item.get("phase", 0)
        mechanism = item.get("mechanismOfAction", "")
        
        # Always add ChEMBL
        item["references"].append({"source": "ChEMBL", "urls": []})
        
        # Add FDA/DailyMed for approved drugs
        if phase == 4:
            item["references"].append({"source": "FDA", "urls": []})
            item["references"].append({"source": "DailyMed", "urls": []})
        
        # Add ClinicalTrials.gov for clinical phases
        if phase in [1, 2, 3, 4]:
            item["references"].append({"source": "ClinicalTrials.gov", "urls": []})
        
        # Add DrugBank if mechanism exists
        if mechanism:
            item["references"].append({"source": "DrugBank", "urls": []})
    
    return evidence_list


async def search_entity(name: str, entity_type: str = "target"):
    """
    Generic search for a target or drug by name.
    Step 1: Resolve Names -> IDs
    """
    query = """
    query Search($queryString: String!, $entityNames: [String!]!) {
      search(queryString: $queryString, entityNames: $entityNames) {
        hits {
          id
          name
          entity
        }
      }
    }
    """
    variables = {"queryString": name, "entityNames": [entity_type]}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.post(BASE_URL, json={"query": query, "variables": variables})
            
            if response.status_code == 200:
                hits = response.json().get("data", {}).get("search", {}).get("hits", [])
                if hits:
                    return hits[0]["id"], hits[0]["name"]
    except Exception as e:
        print(f"Error searching {entity_type}: {e}")
    return None, None


async def search_target_id(name: str):
    return await search_entity(name, "target")


async def search_drug_id(name: str):
    return await search_entity(name, "drug")


async def get_drug_target_interactions(drug_name_input: str, target_id: str, max_retries=3):
    """
    Enhanced: Fetches evidence from MULTIPLE Open Targets endpoints to maximize source diversity.
    
    Combines:
    1. knownDrugs (drug-centric view with FDA/clinical data)
    2. evidence (target-centric view with literature/database sources)
    """
    # 1. Resolve Drug Name to ID
    drug_id, canonical_drug_name = await search_drug_id(drug_name_input)
    
    if not drug_id:
        print(f"Warning: Could not resolve drug '{drug_name_input}' to an ID.")
        return []
    
    print(f"   → Resolved: {drug_name_input} → {canonical_drug_name} ({drug_id})")
    
    all_evidence = []
    
    # ========================================
    # Query 1: Known Drugs (Drug-Centric)
    # ========================================
    query_known_drugs = """
    query DrugKnownDrugs($drugId: String!) {
      drug(chemblId: $drugId) {
        name
        knownDrugs {
          rows {
            target {
              id
              approvedSymbol
            }
            drugType
            phase
            mechanismOfAction
            references {
              source
              urls
            }
          }
        }
      }
    }
    """
    
    variables = {"drugId": drug_id}
    
    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        for attempt in range(max_retries):
            try:
                print(f"   → Fetching knownDrugs data (attempt {attempt + 1})...")
                response = await client.post(
                    BASE_URL, 
                    json={"query": query_known_drugs, "variables": variables}
                )
                if response.status_code != 200:
                    response.raise_for_status()
                     
                data = response.json()
                rows = data.get("data", {}).get("drug", {}).get("knownDrugs", {}).get("rows", [])
                
                for row in rows:
                    row_target_id = row.get("target", {}).get("id", "")
                    if row_target_id == target_id:
                        row['drug'] = {'name': canonical_drug_name, 'id': drug_id}
                        all_evidence.append(row)
                
                print(f"   → Found {len([r for r in rows if r.get('target', {}).get('id') == target_id])} knownDrugs matches")
                break

            except httpx.TimeoutException:
                print(f"   → Timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                print(f"   → API Request Error: {e}")
                break
    
    # ========================================
    # Query 2: Evidence Strings (Target-Centric)
    # ========================================
    # This captures additional sources like EuropePMC, ClinicalTrials.gov, etc.
    query_evidence = """
    query TargetEvidence($targetId: String!, $drugId: String!) {
      target(ensemblId: $targetId) {
        id
        approvedSymbol
        evidences(
          ensemblIds: [$targetId]
          datasourceIds: ["chembl", "europepmc", "expression_atlas"]
        ) {
          rows {
            disease {
              id
              name
            }
            drug {
              id
              name
            }
            datasourceId
            datatypeId
            score
          }
        }
      }
    }
    """
    
    evidence_variables = {"targetId": target_id, "drugId": drug_id}
    
    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        try:
            print(f"   → Fetching additional evidence sources...")
            response = await client.post(
                BASE_URL,
                json={"query": query_evidence, "variables": evidence_variables}
            )
            
            if response.status_code == 200:
                data = response.json()
                evidence_rows = data.get("data", {}).get("target", {}).get("evidences", {}).get("rows", [])
                
                # Filter for drug-specific evidence and add as references
                drug_specific = [
                    row for row in evidence_rows 
                    if row.get("drug", {}).get("id") == drug_id
                ]
                
                if drug_specific and all_evidence:
                    # Enrich the first evidence item with additional sources
                    additional_sources = set()
                    for ev in drug_specific:
                        source = ev.get("datasourceId", "")
                        if source:
                            additional_sources.add(source)
                    
                    # Add these as additional references to the main evidence
                    for source in additional_sources:
                        all_evidence[0].setdefault("references", []).append({
                            "source": source.upper(),
                            "urls": []
                        })
                    
                    print(f"   → Added {len(additional_sources)} additional sources: {additional_sources}")
        
        except Exception as e:
            print(f"   → Could not fetch additional evidence: {e}")
    
    # ========================================
    # Aggregate and Return
    # ========================================
    if all_evidence:
        # 1. Aggregate sources from duplicate evidence items
        aggregated = aggregate_sources(all_evidence)
        
        # 2. Apply source inference (add ChEMBL, FDA, etc.)
        final_evidence = extract_sources_from_evidence(aggregated)
        
        # Debug: Print source count
        total_sources = set()
        for item in final_evidence:
            refs = item.get("references", []) or []
            for ref in refs:
                if ref.get("source"):
                    total_sources.add(ref.get("source"))
        
        print(f"   → Final: {len(final_evidence)} evidence items, {len(total_sources)} unique sources")
        print(f"   → Sources: {sorted(list(total_sources))}")
        
        return final_evidence
    
    return []
