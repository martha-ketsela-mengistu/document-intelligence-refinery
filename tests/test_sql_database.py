import os
import sys
import json

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.db_utils import init_db, insert_facts, query_facts, DB_PATH

def test_sql_database():
    print(f"--- Testing SQL Database at {DB_PATH} ---")
    
    # 1. Initialize
    init_db()
    
    # 2. Prepare sample facts
    sample_facts = [
        {
            "id": "fact_1",
            "doc_id": "test_doc_001",
            "entity": "Commercial Bank of Ethiopia",
            "attribute": "Total Revenue",
            "value": "150000000.00",
            "unit": "ETB",
            "page_number": 1,
            "bbox_json": json.dumps([100, 200, 300, 250]),
            "content_hash": "hash_001"
        },
        {
            "id": "fact_2",
            "doc_id": "test_doc_001",
            "entity": "Commercial Bank of Ethiopia",
            "attribute": "Net Profit",
            "value": "45000000.00",
            "unit": "ETB",
            "page_number": 2,
            "bbox_json": json.dumps([110, 210, 310, 260]),
            "content_hash": "hash_002"
        }
    ]
    
    # 3. Insert
    print(f"Inserting {len(sample_facts)} sample facts...")
    insert_facts(sample_facts)
    
    # 4. Query
    print("Testing 'SELECT * FROM fact_entries'...")
    all_facts = query_facts("SELECT * FROM fact_entries WHERE doc_id = 'test_doc_001'")
    
    if len(all_facts) >= 2:
        print(f"✓ Successfully retrieved {len(all_facts)} facts for 'test_doc_001'.")
    else:
        print(f"✗ Error: Expected at least 2 facts, got {len(all_facts)}.")
        return

    # 5. Complex Query Test
    print("Testing structured query (Total Revenue)...")
    sql = "SELECT value, unit FROM fact_entries WHERE entity = 'Commercial Bank of Ethiopia' AND attribute = 'Total Revenue'"
    revenue = query_facts(sql)
    
    if revenue and revenue[0]['value'] == "150000000.00":
        print(f"✓ Precision query successful: Value={revenue[0]['value']} {revenue[0]['unit']}")
    else:
        print(f"✗ Precision query failed: {revenue}")

    # 6. Provenance Check
    print("Checking provenance data...")
    bbox = json.loads(all_facts[0]['bbox_json'])
    if isinstance(bbox, list) and len(bbox) == 4:
        print(f"✓ Bounding box provenance correctly serialized/deserialized: {bbox}")
    else:
        print(f"✗ Bounding box data corrupted: {all_facts[0]['bbox_json']}")

    print("\n--- SQL Database Test Complete! ---")

if __name__ == "__main__":
    test_sql_database()
