import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.mock_db import db
from app.tools import apply_leave_with_rbac


class HRAgent:
    """
    Persona: You are HR, an intelligent assistant inside EmployeeMate.
    Assist employees with company policy questions, leave balances, and workplace requests.

    Specialist Agent for executing HR operations:
    1. Fetching employee details via get_employee_info(emp_id)
    2. Applying leave via apply_leave(emp_id, start_date, end_date, reason) with RBAC control.
    """
    AGENT_NAME = "HRAgent"
    SYSTEM_INSTRUCTION = "You are HR, an intelligent assistant inside EmployeeMate. Assist employees with company policy questions, leave balances, and workplace requests."

    def __init__(self):
        self.db = db

    def get_employee_info(self, emp_id: str) -> Dict[str, Any]:
        """
        Tool: Fetches employee profile from Mock DB.
        """
        return self.db.get_employee_info(emp_id)

    def apply_leave(self, emp_id: str, start_date: str, end_date: str, reason: str = "Personal", actor_role: str = "EMPLOYEE") -> Dict[str, Any]:
        """
        Tool: Mutates leave balance in Mock DB with RBAC enforcement.
        """
        return apply_leave_with_rbac(emp_id=emp_id, start_date=start_date, end_date=end_date, reason=reason, actor_role=actor_role, db=self.db)

    def process(self, prompt: str, emp_id: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None, actor_role: str = "EMPLOYEE") -> Dict[str, Any]:
        """
        Parses intent from prompt and history, executes appropriate tool(s), and formats result.
        """
        tools_used = []
        
        # Extract emp_id from prompt or history if not directly supplied
        target_emp_id = emp_id
        if not target_emp_id:
            emp_match = re.search(r'\b(EMP\d{3})\b', prompt, re.IGNORECASE)
            if emp_match:
                target_emp_id = emp_match.group(1).upper()
            elif history:
                for past_msg in reversed(history):
                    past_match = re.search(r'\b(EMP\d{3})\b', past_msg.get("content", "") or past_msg.get("text", ""), re.IGNORECASE)
                    if past_match:
                        target_emp_id = past_match.group(1).upper()
                        break

        prompt_lower = prompt.lower()
        is_apply_leave_intent = bool(
            re.search(r'\b(apply|take|book|request|need|want)\b.*\b(leave|leaves|vacation|off)\b', prompt_lower) or
            re.search(r'\b(leave|leaves|vacation|off)\b.*\b(apply|application|request)\b', prompt_lower)
        )

        # Scenario 1: Apply Leave Operation
        if is_apply_leave_intent:
            tools_used.append("apply_leave")

            # First enforce RBAC check for HR persona
            if actor_role and actor_role.upper() == "HR":
                return {
                    "answer": "Access Denied: As HR, you are authorized to view employee leave records and policies, but you cannot submit leave applications on behalf of employees.",
                    "sources": [],
                    "tools_used": tools_used,
                    "agent_routed": self.AGENT_NAME
                }

            if not target_emp_id:
                return {
                    "answer": "Could not execute leave application: Missing employee ID. Please specify an employee ID (e.g., EMP001 or EMP002).",
                    "sources": [],
                    "tools_used": tools_used,
                    "agent_routed": self.AGENT_NAME
                }

            # Parse requested duration (e.g., "10 days", "10 day", "2 days")
            requested_days = None
            days_match = re.search(r'\b(\d+)\s*(?:day|days)\b', prompt, re.IGNORECASE)
            if days_match:
                requested_days = int(days_match.group(1))

            # Parse dates if present or set calculated defaults based on requested days
            dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', prompt)
            if len(dates) >= 2:
                start_date, end_date = dates[0], dates[1]
            elif len(dates) == 1:
                start_date = dates[0]
                num_days = requested_days if requested_days is not None else 1
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = start_dt + timedelta(days=num_days - 1)
                    end_date = end_dt.strftime("%Y-%m-%d")
                except ValueError:
                    end_date = start_date
            else:
                num_days = requested_days if requested_days is not None else 1
                start_dt = datetime.now() + timedelta(days=1)
                end_dt = start_dt + timedelta(days=num_days - 1)
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")

            # Parse reason if provided
            reason = "Personal"
            reason_match = re.search(r'reason[:\s]+(["\']?)([^"\'.]+)\1', prompt, re.IGNORECASE)
            if reason_match:
                reason = reason_match.group(2).strip()

            # Pre-check available balance before calling apply_leave
            info_res = self.get_employee_info(target_emp_id)
            if info_res["status"] == "success":
                emp_data = info_res["data"]
                available_balance = emp_data["leave_balance"]
                
                try:
                    s_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    e_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    calc_days = (e_dt - s_dt).days + 1
                except ValueError:
                    calc_days = 1

                if calc_days > available_balance:
                    return {
                        "answer": f"Leave application rejected: Requested duration of {calc_days} day(s) exceeds your available leave balance of {available_balance} day(s).",
                        "sources": [],
                        "tools_used": tools_used,
                        "agent_routed": self.AGENT_NAME
                    }

            result = self.apply_leave(target_emp_id, start_date, end_date, reason, actor_role=actor_role)
            
            if result["status"] == "success":
                answer = f"Your leave request for {result['days_deducted']} day(s) ({start_date} to {end_date}) has been approved. Your remaining leave balance is {result['remaining_leave_balance']} day(s)."
            else:
                answer = result["message"]

            return {
                "answer": answer,
                "sources": [],
                "tools_used": tools_used,
                "agent_routed": self.AGENT_NAME
            }

        # Scenario 2: Get Employee Info / Leave Balance Query
        tools_used.append("get_employee_info")
        if not target_emp_id:
            return {
                "answer": "Please provide a valid Employee ID (e.g., EMP001 for Rahul or EMP002 for Priya) to fetch HR details.",
                "sources": [],
                "tools_used": tools_used,
                "agent_routed": self.AGENT_NAME
            }

        result = self.get_employee_info(target_emp_id)
        if result["status"] == "success":
            data = result["data"]
            answer = (
                f"Employee Profile for {data['name']} ({data['emp_id']}):\n"
                f"- Department: {data['department']}\n"
                f"- Role: {data['role']}\n"
                f"- Email: {data['email']}\n"
                f"- Leave Balance: {data['leave_balance']} day(s) available."
            )
        else:
            answer = result["message"]

        return {
            "answer": answer,
            "sources": [],
            "tools_used": tools_used,
            "agent_routed": self.AGENT_NAME
        }


hr_agent = HRAgent()

