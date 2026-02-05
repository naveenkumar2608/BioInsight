import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = "https://api.platform.opentargets.org/api/v4/graphql"

def search_entity(name, entity_type):
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
    variables = {"queryString": name, "entityNames": [entity_type] if entity_type else []}
    response = requests.post(BASE_URL, json={"query": query, "variables": variables}, verify=False)
    if response.status_code == 200:
        data = response.json()
        print(f"DEBUG RESPONSE for {name}: {json.dumps(data)[:200]}...")
        hits = data.get("data", {}).get("search", {}).get("hits", [])
        if hits:
            print(f"DEBUG: Top hit for {name}: {hits[0].get('symbol')} / {hits[0].get('name')}")
            return hits[0]
    else:
        print(f"Error: {response.status_code} - {response.text}")
    return None

def get_target_evidence(target_id, drug_name):
    query = """
    query TargetDrugs($targetId: String!) {
      target(ensemblId: $targetId) {
        approvedSymbol
        knownDrugs {
          rows {
            drug {
              id
              name
            }
            mechanismOfAction
            drugType
            references {
              source
              urls
            }
          }
        }
      }
    }
    """
    variables = {"targetId": target_id}
    response = requests.post(BASE_URL, json={"query": query, "variables": variables}, verify=False)
    
    found_evidence = []
    
    if response.status_code == 200:
        data = response.json()
        target_data = data.get("data", {}).get("target", {})
        if not target_data:
            print("No target data found")
            return []
            
        drugs = target_data.get("knownDrugs", {}).get("rows", [])
        print(f"Total known drugs for target: {len(drugs)}")
        
        for row in drugs:
            d_name = row.get("drug", {}).get("name", "")
            print(f"Found Drug in Target: {d_name}")
            if d_name.lower() == drug_name.lower():
                found_evidence.append(row)
                
    return found_evidence

def main():
    drug_name = "Imatinib"
    target_name = "ABL1" 
    
    print(f"Testing with Drug: {drug_name}, Target: {target_name}...")
    
    target_hit = search_entity(target_name, None)
    if not target_hit:
        print("Target not found")
        return
    print(f"Found Target: {target_hit['name']} ({target_hit['id']})")
    
    evidence = get_target_evidence(target_hit['id'], drug_name)
    print(f"Evidence linked to {drug_name}: {len(evidence)}")
    if evidence:
        print("First match:", evidence[0])

if __name__ == "__main__":
    main()
