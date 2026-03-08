import os
import json
from src.agents.query_agent import RefineryAssistant
from src.agents.indexer import NavigationAgent
from src.utils.vector_utils import VectorStoreIngestor
from src.models.navigation import PageIndex

# Load page index
doc_id = "Annual_Report_JUNE-2018.pdf"
index_path = f".refinery/pageindex/{doc_id}.json"

with open(index_path, "r") as f:
    index_data = json.load(f)
    # Pydantic v2 parsing
    page_index = PageIndex(**index_data)

# Initialize Assistant
# Use local ollama
ollama_host = "http://ollama.com"
assistant = RefineryAssistant(ollama_host=ollama_host)

# Test query in Audit Mode
query = "Verify the claim: The combined ratio for 2018 was 78.6%."
print(f"--- Querying Assistant: {query} ---")

# We'll use a manual tool call simulation or run the full graph if possible
# The RefineryAssistant class likely has a method to run the graph
try:
    # Run audit
    result = assistant.run_audit(doc_id, query)
    print("\n--- Audit Result ---")
    print(result)
except Exception as e:
    print(f"Error running audit: {e}")
    # Fallback to direct tool test
    print("\n--- Testing tools directly ---")
    nav = NavigationAgent(ollama_host=ollama_host)
    nodes = nav.query_index(page_index, "combined ratio")
    print(f"Relevant nodes: {[n.title for n in nodes]}")
    
    vec = VectorStoreIngestor()
    results = vec.search(query)
    print(f"Vector search results: {len(results['documents'][0])} matches")
