import os
import sys
import json
from dotenv import load_dotenv
from src.agents.indexer import NavigationAgent
from src.agents.retrieval import RetrievalAgent
from src.agents.query_agent import RefineryAssistant

def test_query_agent():
    load_dotenv()
    doc_id = "2021_Audited_Financial_Statement_Report.pdf"
    ollama_host = os.getenv("OLLAMA_HOST", "https://ollama.com")
    model = os.getenv("OLLAMA_MODEL", "qwen3-vl:235b-instruct") # Use working model
    
    print(f"=== Testing QueryAgent for {doc_id} ===")
    
    # 1. Initialize Agents
    nav_agent = NavigationAgent(ollama_host=ollama_host)
    ret_agent = RetrievalAgent()
    
    # 2. Load PageIndex
    page_index = nav_agent.load_tree(doc_id)
    if not page_index:
        print(f"Error: PageIndex for {doc_id} not found. Run the pipeline first.")
        return
    
    print(f"Loaded PageIndex with {len(page_index.root.child_sections)} top-level sections.")
    
    # 3. Initialize Assistant
    assistant = RefineryAssistant(
        nav_agent=nav_agent, 
        ret_agent=ret_agent, 
        page_index=page_index,
        model=model
    )
    
    # 4. Run sample query
    query = "What is the cash and cash equivalents for the year 2021?"
    print(f"\nQuery: {query}")
    answer = assistant.run(query)
    print(f"\nAnswer:\n{answer}")
    
    # 5. Run Audit Mode
    claim = "The company reported a cash and cash equivalents of 15,194,080,000 Birr for the year 2021."
    print(f"\nAudit Claim: {claim}")
    audit_result = assistant.audit_claim(claim)
    print(f"\nAudit Result:\n{audit_result}")

if __name__ == "__main__":
    # Ensure project root is in path
    sys.path.append(os.getcwd())
    test_query_agent()
