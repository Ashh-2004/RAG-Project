from typing import Dict, Any, List, Optional
from app.rag import rag_pipeline, RAGPipeline
from app.tools import search_company_documents


class KnowledgeAgent:
    """
    Specialist Agent for company policies, WFH guidelines, travel rules,
    IT security, and general document retrieval using 2-Stage RAG tools with metadata filtering.
    """
    AGENT_NAME = "KnowledgeAgent"
    TOOL_NAME = "RAG_Policy_Search"

    def __init__(self):
        self.rag = rag_pipeline

    def _infer_category(self, prompt: str) -> Optional[str]:
        prompt_lower = prompt.lower()
        matches = []
        if any(term in prompt_lower for term in ["wfh", "remote", "work from home"]):
            matches.append("wfh")
        if any(term in prompt_lower for term in ["leave policy", "annual leave", "vacation policy", "sick leave"]):
            matches.append("leave")
        if any(term in prompt_lower for term in ["travel", "per diem", "flight", "hotel", "reimbursement"]):
            matches.append("travel")
        if any(term in prompt_lower for term in ["security", "password", "wifi", "vpn", "cybersecurity"]):
            matches.append("it_security")

        if len(matches) == 1:
            return matches[0]
        return None

    def process(self, prompt: str, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a user query by querying the 2-Stage RAG pipeline.
        Returns standard dictionary with answer, sources, tools_used, and agent_routed.
        """
        if not category:
            category = self._infer_category(prompt)

        tool_res = search_company_documents(query=prompt, category=category)
        answer = tool_res["answer"]
        sources = tool_res["sources"]

        # If answer indicates missing context, ensure sources is empty list
        if answer == RAGPipeline.STRICT_NOT_FOUND_MSG:
            sources = []

        return {
            "answer": answer,
            "sources": sources,
            "tools_used": [self.TOOL_NAME],
            "agent_routed": self.AGENT_NAME
        }


knowledge_agent = KnowledgeAgent()

