
import asyncio
import httpx
import json

BASE_URL = "https://api.platform.opentargets.org/api/v4/graphql"

async def search_full_query(query_str: str, entity_type: str):
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
    variables = {"queryString": query_str, "entityNames": [entity_type]}
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        response = await client.post(BASE_URL, json={"query": query, "variables": variables})
        if response.status_code == 200:
            hits = response.json().get("data", {}).get("search", {}).get("hits", [])
            print(f"Hits for '{query_str}' ({entity_type}): {[h['name'] for h in hits[:3]]}")
            return hits
    return []

async def test():
    query = "How does Omeprazole interact with ATP4A?"
    await search_full_query(query, "drug")
    await search_full_query(query, "target")

if __name__ == "__main__":
    asyncio.run(test())
