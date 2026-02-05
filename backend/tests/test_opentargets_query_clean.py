
import asyncio
import httpx
import json
import re

BASE_URL = "https://api.platform.opentargets.org/api/v4/graphql"

def get_clean_search_string(text: str) -> str:
    stopwords = {
        'how', 'does', 'with', 'is', 'the', 'and', 'what', 'tell', 'me', 
        'about', 'of', 'on', 'in', 'to', 'for', 'a', 'an', 'are', 'was', 'were',
        'has', 'have', 'had', 'been', 'be', 'by', 'at', 'from', 'this', 'that',
        'which', 'who', 'whom', 'whose', 'its', 'interact', 'interaction', 
        'mechanistically', 'mechanism', 'acts', 'acts on', 'between', 'relationship'
    }
    # Remove symbols and split
    words = re.sub(r'[^\w\s-]', ' ', text).split()
    # Filter stopwords
    filtered = [w for w in words if w.lower() not in stopwords]
    return " ".join(filtered)

async def search_full_query(query_str: str, entity_type: str):
    clean_query = get_clean_search_string(query_str)
    print(f"Cleaned query: '{clean_query}'")
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
    variables = {"queryString": clean_query, "entityNames": [entity_type]}
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        response = await client.post(BASE_URL, json={"query": query, "variables": variables})
        if response.status_code == 200:
            hits = response.json().get("data", {}).get("search", {}).get("hits", [])
            print(f"Hits for '{clean_query}' ({entity_type}): {[h['name'] for h in hits[:5]]}")
            return hits
    return []

async def test():
    query = "How does Omeprazole interact with ATP4A?"
    await search_full_query(query, "drug")
    await search_full_query(query, "target")

if __name__ == "__main__":
    asyncio.run(test())
