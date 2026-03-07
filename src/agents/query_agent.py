import os
import json
from typing import List, Optional, Annotated, TypedDict, Union, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from ..agents.indexer import NavigationAgent
from ..agents.retrieval import RetrievalAgent
from ..utils.db_utils import query_facts
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

# --- Global / Registry for agents to be used by tools ---
# In a production system, these would be passed via config or state
_NAV_AGENT: Optional[NavigationAgent] = None
_RET_AGENT: Optional[RetrievalAgent] = None
_PAGE_INDEX: Optional[Any] = None

@tool
def pageindex_navigate(query: str):
    """
    Search the document's hierarchical PageIndex to find relevant sections and summaries.
    Useful for high-level navigation and locating where specific topics are discussed.
    """
    if not _NAV_AGENT or not _PAGE_INDEX:
        return "Error: PageIndex not initialized."
    nodes = _NAV_AGENT.query_index(_PAGE_INDEX, query)
    results = []
    for n in nodes:
        results.append({
            "title": n.title,
            "pages": f"{n.page_start}-{n.page_end}",
            "summary": n.summary,
            "entities": n.key_entities
        })
    return json.dumps(results, indent=2)

@tool
def semantic_search(query: str, sections: Optional[List[str]] = None):
    """
    Perform a vector-based semantic search over document chunks (LDUs).
    You can optionally filter by section titles found via pageindex_navigate.
    Returns text content with page numbers and bounding boxes for provenance.
    """
    if not _RET_AGENT:
        return "Error: RetrievalAgent not initialized."
    
    results = _RET_AGENT.search(query, top_k=5, section_filter=sections)
    formatted = []
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        formatted.append({
            "content": doc,
            "page": meta.get('pages', 'N/A'),
            "section": meta.get('section', 'N/A'),
            "bbox": meta.get('bbox', 'N/A'),
            "doc_id": meta.get('doc_id', 'Unknown')
        })
    return json.dumps(formatted, indent=2)

@tool
def fact_verification(entity_keyword: str, attribute_keyword: str):
    """
    Search for structured facts using keywords for entity and attribute.
    Useful for verification when you know the keywords but are unsure of the exact spelling, case, or unit format in the database.
    Example: fact_verification("Cash", "2021")
    """
    sql = "SELECT entity, attribute, value, unit, page_number, doc_id FROM fact_entries WHERE entity LIKE ? AND attribute LIKE ?"
    params = (f"%{entity_keyword}%", f"%{attribute_keyword}%")
    results = query_facts(sql, params)
    return json.dumps(results, indent=2)

@tool
def structured_query(sql: str):
    """
    Execute a SQLite query against the 'fact_entries' table.
    The table schema is: (id, doc_id, entity, attribute, value, unit, page_number, bbox_json, content_hash).
    Useful for precise numerical questions (e.g., 'What was the total expense for CBE?').
    """
    results = query_facts(sql)
    if not results:
        return "Query returned no results. Please check your SQL syntax or data availability and do not repeat the exact same query."
    return json.dumps(results, indent=2)

# --- Agent State & Graph ---

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]

class RefineryAssistant:
    def __init__(self, nav_agent: NavigationAgent, ret_agent: RetrievalAgent, page_index: Any, model: str = "qwen3-vl:235b-instruct"):
        global _NAV_AGENT, _RET_AGENT, _PAGE_INDEX
        _NAV_AGENT = nav_agent
        _RET_AGENT = ret_agent
        _PAGE_INDEX = page_index
        
        self.llm = ChatOllama(
            model=model, 
            temperature=0,
            base_url=os.getenv("OLLAMA_HOST", "https://ollama.com")
        ).bind_tools([
            pageindex_navigate, 
            semantic_search, 
            structured_query,
            fact_verification
        ])
        
        # Define the graph
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode([
            pageindex_navigate, 
            semantic_search, 
            structured_query,
            fact_verification
        ]))
        
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        workflow.add_edge("tools", "agent")
        
        self.app = workflow.compile()

    def _should_continue(self, state: AgentState):
        last_message = state["messages"][-1]
        if not last_message.tool_calls:
            return "end"
        return "continue"

    def _call_model(self, state: AgentState):
        from langchain_core.messages import SystemMessage
        # System message to enforce provenance and tool usage
        system_msg = SystemMessage(content="""
You are the Document Intelligence Refinery Assistant. You help users query complex documents.
CRITICAL INSTRUCTION: You MUST ALWAYS include source citations (doc_id, page_number) in your final answer for EVERY fact or claim you state.
Format your citations strictly as: [Doc: <doc_id>, Page: <page_number>]

TOOL USAGE GUIDELINES:
1. Use 'pageindex_navigate' first to understand the document structure and identify relevant section titles.
2. Use 'fact_verification' for claim auditing and finding structured facts when you are unsure of the exact format.
   - It performs fuzzy matching on entity and attribute.
   - Example: If verifying cash in 2021, use fact_verification(entity_keyword="Cash", attribute_keyword="2021").
3. Use 'structured_query' for precise SQL when you are confident in the schema and values.
4. Use 'semantic_search' for textual details or when structured tools fail.

CRITICAL Provenance Rules:
- You MUST use the EXACT 'doc_id' string returned by the tools.
- VALUE NORMALIZATION: If a tool returns a value like 15194080 with unit "Birr'000", recognize that it actually means 15,194,080,000 Birr. Explain this calculation in your answer.
- Without citations, your answer is invalid. Be precise and cite your sources exactly using the metadata returned by the tools.
""")
        # Prepend system message
        messages = [system_msg] + state["messages"]
        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def run(self, query: str):
        inputs = {"messages": [HumanMessage(content=query)]}
        final_state = self.app.invoke(inputs, config={"recursion_limit": 10})
        return final_state["messages"][-1].content

    def audit_claim(self, claim: str) -> str:
        """
        Audit Mode: Verify a claim against the document.
        Returns the verification with source citation or 'unverifiable'.
        """
        prompt = f"Verify the following claim against the document data. If verified, provide the Doc ID and Page Number. If it cannot be verified, state 'unverifiable'.\n\nClaim: {claim}"
        return self.run(prompt)
