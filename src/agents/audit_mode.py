from typing import List, Dict, Any
from ..agents.assistant import RefineryAssistant
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

class AuditMode:
    def __init__(self, assistant: RefineryAssistant):
        self.assistant = assistant

    def verify_claim(self, claim: str) -> Dict[str, Any]:
        """
        Verify a specific claim against the refinery's data.
        Returns a structured result with verification status and provenance.
        """
        logger.info(f"Audit Mode: Verifying claim -> {claim}")
        
        system_prompt = f"""
        You are in AUDIT MODE. Your goal is to verify or debunk the following CLAIM:
        CLAIM: "{claim}"
        
        Follow these steps:
        1. Search for relevant sections using the PageIndex.
        2. Perform a structured query if the claim is numerical/financial.
        3. Perform a semantic search for context and supporting text.
        4. Based ONLY ON THE RETRIEVED DATA, decide:
           - VERIFIED: If the claim is supported.
           - FLAGGED: If the claim contradicts the data.
           - NOT FOUND / UNVERIFIABLE: If no data supports or debunks it.
        
        CRITICAL INSTRUCTION: You MUST include source citations containing the EXACT doc_id, page, and bbox from the tool outputs.
        Your final response MUST be a JSON object:
        {{
            "status": "VERIFIED" | "FLAGGED" | "NOT FOUND",
            "reasoning": "...",
            "citations": [
                {{
                    "doc_id": "...",
                    "page": "...",
                    "bbox": "...",
                    "text": "..."
                }}
            ]
        }}
        Output ONLY the strict JSON object, with no markdown formatting or conversational text.
        """
        
        # We run the assistant with this specific audit context
        # Note: RefineryAssistant.run needs to handle this specific instruction or we just invoke it with the claim
        # For this implementation, we'll use the assistant's underlying app.invoke directly to pass the audit instruction
        
        from langchain_core.messages import HumanMessage
        
        inputs = {"messages": [HumanMessage(content=system_prompt)]}
        try:
            # We'll use the Assistant's already initialized app with a recursion limit to prevent looping
            response = self.assistant.app.invoke(inputs, config={"recursion_limit": 10})
            final_msg = response["messages"][-1].content
            
            # Parse the JSON from the assistant's response
            import json
            start = final_msg.find("{")
            end = final_msg.rfind("}") + 1
            if start != -1 and end != -1:
                return json.loads(final_msg[start:end])
            
            return {
                "status": "NOT FOUND",
                "reasoning": f"Could not parse assistant response: {final_msg}",
                "citations": []
            }
            
        except Exception as e:
            logger.error(f"Audit verification failed: {str(e)}")
            return {
                "status": "ERROR",
                "reasoning": str(e),
                "citations": []
            }
