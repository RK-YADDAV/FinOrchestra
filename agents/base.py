import os
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional
from google import genai
from core.context import SharedState
from core.budget import ContextBudgetManager


class BaseAgent(ABC):
    # Default model for all agents — change this ONE place to switch models globally
    DEFAULT_MODEL = "gemini-3.8-flash"

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        api_key = os.environ.get(f"GOOGLE_API_KEY_{agent_id.upper()}") or os.environ.get("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)

    async def _call_llm(self, contents: str, config: Optional[dict] = None, max_retries: int = 4):
        """Call Gemini with automatic retry on 503/429 errors (exponential backoff)."""
        kwargs = {"model": self.DEFAULT_MODEL, "contents": contents}
        if config:
            kwargs["config"] = config

        last_error = None
        for attempt in range(max_retries):
            try:
                resp = await asyncio.to_thread(
                    self.client.models.generate_content, **kwargs
                )
                return resp
            except Exception as e:
                last_error = e
                err_str = str(e)
                # Retry only on transient server errors (503, 429)
                if "503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = (2 ** attempt) + 1  # 2s, 3s, 5s, 9s
                    print(f"[{self.agent_id}] Gemini API overloaded (attempt {attempt+1}/{max_retries}), retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise  # Non-transient error, raise immediately
        raise last_error  # All retries exhausted

    @abstractmethod
    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        pass
