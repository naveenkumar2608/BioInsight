import sqlite3

def view_db():
    conn = sqlite3.connect('drug_target.db')
    cursor = conn.cursor()
    
    tables = ['drugs', 'targets', 'interactions']
    
    for table in tables:
        print(f"--- {table.upper()} TABLE (Sample 5 rows) ---")
        cursor.execute(f"SELECT * FROM {table} LIMIT 5")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [col[1] for col in cursor.fetchall()]
        print(f"Columns: {cols}")
        
        for row in rows:
            print(row)
        print("\n")
    
    conn.close()

if __name__ == "__main__":
    view_db()
