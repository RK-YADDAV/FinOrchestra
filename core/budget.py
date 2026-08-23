import asyncio
import os
from typing import Dict, Optional
from google import genai
from core.context import SharedState


class BudgetOverflowError(Exception):
    pass


class ContextBudgetManager:
    DEFAULT_BUDGETS: Dict[str, int] = {
        "orchestrator": 2048,
        "decomposition": 3072,
        "retrieval": 6144,
        "quant_runner": 4096,
        "auditor_synthesizer": 6144,
    }

    def __init__(self, state: SharedState, redis_pub=None):
        self._state = state
        self._redis_pub = redis_pub
        self._lock = asyncio.Lock()
        api_key = os.environ.get("GOOGLE_API_KEY_ORCHESTRATOR") or os.environ.get("GOOGLE_API_KEY")
        self._client = genai.Client(api_key=api_key)
        self.budgets: Dict[str, Dict[str, int]] = {
            agent: {"max": max_t, "used": 0} 
            for agent, max_t in self.DEFAULT_BUDGETS.items()
        }

    def count_tokens(self, text: str) -> int:
        try:
            resp = self._client.models.count_tokens(model="gemini-2.5-flash", contents=text)
            return max(1, resp.total_tokens)
        except Exception:
            return max(1, len(text) // 4)

    def preflight_check(self, agent_id: str, text: str) -> bool:
        needed = self.count_tokens(text)
        entry = self.budgets.get(agent_id, {"max": 4096, "used": 0})
        return (entry["used"] + needed) <= entry["max"]

    async def consume(self, agent_id: str, text: str) -> None:
        tokens = self.count_tokens(text)
        async with self._lock:
            if agent_id in self.budgets:
                self.budgets[agent_id]["used"] += tokens
            self._state.used_tokens += tokens

        if self._redis_pub:
            await self._redis_pub.publish(self._state.job_id, {
                "event_type": "BUDGET_UPDATE",
                "agent_id": agent_id,
                "used_tokens": self.budgets[agent_id]["used"],
                "max_tokens": self.budgets[agent_id]["max"],
                "total_used": self._state.used_tokens,
                "total_max": self._state.max_tokens,
            })

    def assert_compliant(self, agent_id: str) -> None:
        entry = self.budgets.get(agent_id)
        if entry and entry["used"] > entry["max"]:
            raise BudgetOverflowError(f"Agent '{agent_id}' exceeded allocated budget: {entry['used']}/{entry['max']} tokens")
