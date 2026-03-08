import sqlite3
import os

db_path = ".refinery/refinery.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM fact_entries;")
    count = cursor.fetchone()[0]
    print(f"Total fact entries in SQLite: {count}")
    
    cursor.execute("SELECT * FROM fact_entries LIMIT 5;")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()
else:
    print("Database not found.")
