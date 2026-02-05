import sqlite3
import os
import re
from tqdm import tqdm

def parse_ttd_data():
    print("Starting TTD Data Extraction...")
    
    db_path = "drug_target.db"
    
    # Remove existing db if it exists to start fresh
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS drugs (
        drug_id TEXT PRIMARY KEY,
        name TEXT,
        company TEXT,
        therapeutic_class TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS targets (
        target_id TEXT PRIMARY KEY,
        name TEXT,
        symbol TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id TEXT,
        drug_id TEXT,
        drug_name TEXT,
        clinical_phase TEXT
    )
    ''')

    # Indices for faster lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_drug_name ON drugs(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_target_symbol ON targets(symbol)")

    # 1. Parse Drugs (to get metadata like company/class)
    drug_file = "P1-02-TTD_drug_download.txt"
    if os.path.exists(drug_file):
        print(f"Parsing {drug_file}...")
        current_drug = {}
        with open(drug_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 3:
                    continue
                
                did, tag, val = parts[0], parts[1], parts[2]
                
                if 'id' not in current_drug or current_drug['id'] != did:
                    if 'id' in current_drug:
                        cursor.execute("INSERT OR REPLACE INTO drugs (drug_id, name, company, therapeutic_class) VALUES (?, ?, ?, ?)",
                                     (current_drug['id'], current_drug.get('name'), current_drug.get('company'), current_drug.get('class')))
                    current_drug = {'id': did}
                
                if tag == 'DRUG__ID':
                    current_drug['id'] = val
                elif tag == 'TRADNAME':
                    current_drug['name'] = val
                elif tag == 'DRUGCOMP':
                    current_drug['company'] = val
                elif tag == 'THERCLAS':
                    current_drug['class'] = val
            
            # Insert last drug
            if 'id' in current_drug:
                cursor.execute("INSERT OR REPLACE INTO drugs (drug_id, name, company, therapeutic_class) VALUES (?, ?, ?, ?)",
                             (current_drug['id'], current_drug.get('name'), current_drug.get('company'), current_drug.get('class')))

    # 2. Parse Targets and Interactions (AND update drug names)
    target_file = "P1-01-TTD_target_download.txt"
    if os.path.exists(target_file):
        print(f"Parsing {target_file}...")
        current_target = {}
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 3:
                    continue
                
                tid, tag, val = parts[0], parts[1], parts[2]
                
                if 'id' not in current_target or current_target['id'] != tid:
                    if 'id' in current_target:
                        cursor.execute("INSERT OR REPLACE INTO targets (target_id, name, symbol) VALUES (?, ?, ?)",
                                     (current_target['id'], current_target.get('name'), current_target.get('symbol')))
                    current_target = {'id': tid}
                
                if tag == 'TARGETID':
                    current_target['id'] = val
                elif tag == 'TARGNAME':
                    current_target['name'] = val
                elif tag == 'TARG_SYM':
                    current_target['symbol'] = val
                elif tag == 'DRUGINFO':
                    if len(parts) >= 5:
                        d_id = parts[2]
                        d_name = parts[3]
                        d_phase = parts[4]
                        
                        # Save interaction
                        cursor.execute("INSERT INTO interactions (target_id, drug_id, drug_name, clinical_phase) VALUES (?, ?, ?, ?)",
                                     (tid, d_id, d_name, d_phase))
                        
                        # CRITICAL: Update drug name in drugs table if not already set
                        # We use UPDATE here because 'add' already inserted IDs from P1-02
                        cursor.execute("UPDATE drugs SET name = ? WHERE drug_id = ? AND name IS NULL", (d_name, d_id))
                        # If drug didn't exist in P1-02 (rare but possible), create it
                        cursor.execute("INSERT OR IGNORE INTO drugs (drug_id, name) VALUES (?, ?)", (d_id, d_name))

                    elif len(parts) == 4:
                        d_id = parts[2]
                        d_name = parts[3]
                        cursor.execute("INSERT INTO interactions (target_id, drug_id, drug_name, clinical_phase) VALUES (?, ?, ?, ?)",
                                     (tid, d_id, d_name, "Unknown"))
                        cursor.execute("UPDATE drugs SET name = ? WHERE drug_id = ? AND name IS NULL", (d_name, d_id))
                        cursor.execute("INSERT OR IGNORE INTO drugs (drug_id, name) VALUES (?, ?)", (d_id, d_name))

            # Insert last target
            if 'id' in current_target:
                cursor.execute("INSERT OR REPLACE INTO targets (target_id, name, symbol) VALUES (?, ?, ?)",
                             (current_target['id'], current_target.get('name'), current_target.get('symbol')))

    conn.commit()
    
    # Final counts
    cursor.execute("SELECT COUNT(*) FROM drugs")
    drug_count_total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM drugs WHERE name IS NOT NULL")
    drug_count_named = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM targets")
    target_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM interactions")
    int_count = cursor.fetchone()[0]
    
    print(f"Successfully created drug_target.db")
    print(f"Total Drugs: {drug_count_total}")
    print(f"Named Drugs: {drug_count_named}")
    print(f"Targets: {target_count}")
    print(f"Interactions: {int_count}")
    
    conn.close()

if __name__ == "__main__":
    parse_ttd_data()
