import sqlite3
import chromadb
import os
import json
from tqdm import tqdm

def populate():
    print("Starting ChromaDB population...")
    
    db_path = "drug_target.db"
    # Initialize ChromaDB
    persist_directory = "chroma_db"
    client = chromadb.PersistentClient(path=persist_directory)
    
    # 1. Collection for Drugs
    print("Populating Drugs collection...")
    drug_collection = client.get_or_create_collection(name="drugs")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT drug_id, name, therapeutic_class FROM drugs WHERE name IS NOT NULL")
    drugs = cursor.fetchall()
    print(f"Total drugs in SQLite: {len(drugs)}")
    
    batch_size = 100 # Smaller batch for more feedback
    for i in tqdm(range(0, len(drugs), batch_size), desc="Drugs"):
        batch = drugs[i:i+batch_size]
        ids = [d[0] for d in batch]
        documents = [d[1] for d in batch]
        metadatas = [{"therapeutic_class": d[2] or ""} for d in batch]
        drug_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    # 2. Collection for Targets
    print("Populating Targets collection...")
    target_collection = client.get_or_create_collection(name="targets")
    cursor.execute("SELECT target_id, name, symbol FROM targets WHERE name IS NOT NULL")
    targets = cursor.fetchall()
    print(f"Total targets in SQLite: {len(targets)}")
    
    for i in tqdm(range(0, len(targets), batch_size), desc="Targets"):
        batch = targets[i:i+batch_size]
        ids = [t[0] for t in batch]
        documents = [f"{t[1]} ({t[2]})" if t[2] else t[1] for t in batch]
        metadatas = [{"name": t[1], "symbol": t[2] or ""} for t in batch]
        target_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    print("ChromaDB population complete!")
    conn.close()

if __name__ == "__main__":
    populate()
