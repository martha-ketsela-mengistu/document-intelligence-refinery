import sqlite3
import os
from typing import List, Dict, Any
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

DB_PATH = ".refinery/refinery.db"

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Fact entries table with provenance
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_entries (
            id TEXT PRIMARY KEY,
            doc_id TEXT,
            entity TEXT,
            attribute TEXT,
            value TEXT,
            unit TEXT,
            page_number INTEGER,
            bbox_json TEXT,
            content_hash TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized with fact_entries table.")

def insert_facts(facts: List[Dict[str, Any]]):
    """Insert a list of facts into the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        for fact in facts:
            cursor.execute("""
                INSERT OR REPLACE INTO fact_entries 
                (id, doc_id, entity, attribute, value, unit, page_number, bbox_json, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fact.get("id"),
                fact.get("doc_id"),
                fact.get("entity"),
                fact.get("attribute"),
                fact.get("value"),
                fact.get("unit"),
                fact.get("page_number"),
                fact.get("bbox_json"),
                fact.get("content_hash")
            ))
        conn.commit()
        logger.info(f"Inserted {len(facts)} facts into the database.")
    except Exception as e:
        logger.error(f"Error inserting facts: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

def query_facts(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a read-only query and return results as list of dicts."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        logger.info(f"Executing SQL query: {sql} with params {params}")
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"SQL Query failed: {str(e)}")
        return []
    finally:
        conn.close()
