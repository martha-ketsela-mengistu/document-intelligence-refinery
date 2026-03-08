import sqlite3
import sys
import os

DB_PATH = ".refinery/refinery.db"

def list_entities():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("\n--- Extracted Entities ---")
    for row in cursor.execute("SELECT DISTINCT entity FROM fact_entries ORDER BY entity"):
        print(row[0])
    conn.close()

def search_entity(name):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    print(f"\n--- Facts for Entity matching '{name}' ---")
    query = "SELECT entity, attribute, value, unit, page_number FROM fact_entries WHERE entity LIKE ?"
    for row in cursor.execute(query, (f"%{name}%",)):
        print(f"[{row['page_number']}] {row['entity']} | {row['attribute']}: {row['value']} {row['unit']}")
    conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)
        
    if len(sys.argv) > 1:
        search_entity(sys.argv[1])
    else:
        list_entities()
        print("\nUsage: python tools/db_explorer.py <entity_name_keyword>")
