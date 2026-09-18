import re
from typing import Dict, Any, List, Optional
from app.agents.knowledge_agent import knowledge_agent
from app.agents.hr_agent import hr_agent


class OrchestratorRouter:
    """
    Orchestrator Router responsible for analyzing user intent and routing:
    - KnowledgeAgent (for company policy / RAG queries)
    - HRAgent (for HR database queries / leave applications)
    - BOTH (Multi-Tool reasoning for hybrid queries)
    Aggregates answers, sources, and executed tool names.
    """

    def __init__(self):
        self.knowledge_agent = knowledge_agent
        self.hr_agent = hr_agent

    def route_and_execute(self, prompt: str, emp_id: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None, actor_role: str = "EMPLOYEE") -> Dict[str, Any]:
        """
        Determines routing target, invokes agent(s), and returns consolidated response.
        Forwards actor_role to HRAgent for RBAC enforcement.
        """
        prompt_lower = prompt.lower()

        # Explicit HR intent keywords in prompt
        hr_keywords = [
            "leave", "leaves", "apply", "balance", "vacation", "profile",
            "employee", "my info", "who am i", "sick leave", "casual leave", "annual leave"
        ]
        prompt_has_emp_mention = bool(re.search(r'\bEMP\d{3}\b', prompt, re.IGNORECASE))
        is_hr_intent = prompt_has_emp_mention or any(re.search(r'\b' + re.escape(kw) + r'\b', prompt_lower) for kw in hr_keywords)

        # Knowledge / Policy keywords
        knowledge_keywords = [
            "policy", "wfh", "work from home", "travel", "allowance", "per diem",
            "security", "password", "vpn", "mfa", "guidelines", "entitlement", "reimbursement", "rules"
        ]
        is_knowledge_intent = any(kw in prompt_lower for kw in knowledge_keywords)

        # Decision Matrix
        if is_hr_intent and is_knowledge_intent:
            return self._execute_both(prompt, emp_id, history, actor_role=actor_role)
        elif is_hr_intent:
            return self.hr_agent.process(prompt, emp_id=emp_id, history=history, actor_role=actor_role)
        elif is_knowledge_intent:
            return self.knowledge_agent.process(prompt)
        else:
            # Check if prompt contains leave application intent without explicitly having 'policy'
            if "leave" in prompt_lower or "balance" in prompt_lower:
                return self.hr_agent.process(prompt, emp_id=emp_id, history=history, actor_role=actor_role)
            # Default to Knowledge Agent
            return self.knowledge_agent.process(prompt)

    def _execute_both(self, prompt: str, emp_id: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None, actor_role: str = "EMPLOYEE") -> Dict[str, Any]:
        """
        Multi-Tool reasoning: Invokes KnowledgeAgent and HRAgent, then aggregates results.
        Forwards actor_role to HRAgent for RBAC enforcement.
        """
        knowledge_res = self.knowledge_agent.process(prompt)
        hr_res = self.hr_agent.process(prompt, emp_id=emp_id, history=history, actor_role=actor_role)

        # Aggregate answers sequentially
        answers = []
        if knowledge_res.get("answer"):
            answers.append(knowledge_res["answer"])

        if hr_res.get("answer"):
            answers.append(hr_res["answer"])

        combined_answer = "\n\n".join(answers)

        # Aggregate deduplicated sources
        aggregated_sources = list(dict.fromkeys(knowledge_res.get("sources", []) + hr_res.get("sources", [])))

        # Aggregate deduplicated tools
        aggregated_tools = list(dict.fromkeys(knowledge_res.get("tools_used", []) + hr_res.get("tools_used", [])))

        return {
            "answer": combined_answer,
            "sources": aggregated_sources,
            "tools_used": aggregated_tools,
            "agent_routed": "Orchestrator_MultiAgent"
        }


orchestrator = OrchestratorRouter()
