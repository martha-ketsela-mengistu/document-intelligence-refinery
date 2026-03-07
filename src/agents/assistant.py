import os
import json
from typing import List, Optional, Annotated, TypedDict, Union, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from ..agents.navigation import NavigationAgent
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
            structured_query
        ])
        
        # Define the graph
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode([
            pageindex_navigate, 
            semantic_search, 
            structured_query
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
CRITICAL INSTRUCTION: You MUST ALWAYS include source citations (doc_id, page_number, bounding box) in your final answer for EVERY fact or claim you state.
Format your citations strictly as: [Doc: <doc_id>, Page: <page_number>, BBox: <bbox>]
Use 'pageindex_navigate' first to understand the document structure.
Use 'structured_query' for numerical or financial facts.
Use 'semantic_search' for textual details.
Without citations, your answer is invalid. Be precise and cite your sources exactly using the metadata returned by the tools.
""")
        # Prepend system message
        messages = [system_msg] + state["messages"]
        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def run(self, query: str):
        inputs = {"messages": [HumanMessage(content=query)]}
        final_state = self.app.invoke(inputs, config={"recursion_limit": 10})
        return final_state["messages"][-1].content
