import json
import asyncio
from core.context import SharedState, SubTask
from core.budget import ContextBudgetManager
from agents.base import BaseAgent

DECOMPOSITION_PROMPT = """You are an Indian Equity Research Planner.
Break the financial query into 2-5 typed subtasks with explicit dependencies.

Query: {query}
Company: {company} | Ticker: {ticker}

Allowed Task Types:
- filing_rag: Balance Sheet, P&L, Cash Flow, MDA, Notes to Accounts (BSE/NSE Annual Reports, SEBI LODR 33).
- concall_rag: Management commentary, margin guidance, CapEx execution.
- market_quote: Live CMP, P/E, Market Cap in \u20b9 Cr, Promoters' Pledge % from NSE/BSE.
- quant_calc: Python calculation in \u20b9 Cr (ROCE, ROE, Free Cash Flow, Debt/Equity).

Return JSON:
{{
  "sub_tasks": [
    {{"id": "t1", "title": "Retrieve Standalone vs Consolidated Debt from FY25 Annual Report", "task_type": "filing_rag", "deps": []}},
    {{"id": "t2", "title": "Compute FY25 ROCE in \u20b9 Crores", "task_type": "quant_calc", "deps": ["t1"]}}
  ]
}}"""

class DecompositionAgent(BaseAgent):
    def __init__(self):
        super().__init__("decomposition")

    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        prompt = DECOMPOSITION_PROMPT.format(query=state.query, company=state.company or "", ticker=state.ticker or "")
        await budget_mgr.consume(self.agent_id, prompt)

        resp = await self._call_llm(
            prompt,
            config={"response_mime_type": "application/json"}
        )
        try:
            data = json.loads(resp.text)
        except Exception:
            # Fallback parsing
            clean_text = resp.text.strip().strip('```json').strip('```').strip()
            data = json.loads(clean_text)
            
        subtasks = [SubTask(**t) for t in data.get("sub_tasks", [])]

        # Verify no circular dependencies exist
        self._verify_no_cycles(subtasks)
        state.subtasks = subtasks
        state.add_event(self.agent_id, "DECOMPOSITION_DONE", {"subtasks_count": len(subtasks)})

    def _verify_no_cycles(self, subtasks: list[SubTask]) -> None:
        visited, rec_stack = set(), set()
        task_map = {t.id: t.deps for t in subtasks}
        def dfs(node):
            visited.add(node); rec_stack.add(node)
            for dep in task_map.get(node, []):
                if dep not in visited:
                    if dfs(dep): return True
                elif dep in rec_stack: return True
            rec_stack.discard(node); return False
        for tid in task_map:
            if tid not in visited and dfs(tid):
                raise ValueError(f"Circular dependency detected involving task '{tid}'")
