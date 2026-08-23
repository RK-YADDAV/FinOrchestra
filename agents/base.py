import os
from abc import ABC, abstractmethod
from typing import Optional
from google import genai
from core.context import SharedState
from core.budget import ContextBudgetManager


class BaseAgent(ABC):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        api_key = os.environ.get(f"GOOGLE_API_KEY_{agent_id.upper()}") or os.environ.get("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)

    @abstractmethod
    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        pass
