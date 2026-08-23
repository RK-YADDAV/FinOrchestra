import json
import asyncio
from core.context import SharedState
from core.budget import ContextBudgetManager
from agents.base import BaseAgent

ORCHESTRATOR_PROMPT = """You are the Master Orchestrator for FinOrchestra India (ArthGraph).
Decide which agent to invoke next based on the blackboard state.

DEFAULT ROUTING RULES:
1. turn == 0 -> "decomposition"
2. decomposition done, chunks empty -> "retrieval"
3. chunks retrieved, financial calculations empty -> "quant_runner"
4. chunks & calculations ready -> "auditor_synthesizer"
5. memo generated -> "done"

HARD CONSTRAINTS:
- Max turns: 10.
- Deviations allowed only with explicit financial reasoning.

Return JSON:
{"next_agent": "decomposition|retrieval|quant_runner|auditor_synthesizer|done", "reasoning": "...", "confidence": 0.95}"""

class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("orchestrator")

    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> str:
        # Simple rule-based fast path routing for common flows to save tokens
        if state.turn == 0:
            next_agent = "decomposition"
            reasoning = "Initial turn, delegating to decomposition"
        elif state.subtasks and not state.chunks:
            next_agent = "retrieval"
            reasoning = "Subtasks created, need to retrieve filings"
        elif state.chunks and not state.calculations:
            next_agent = "quant_runner"
            reasoning = "Chunks retrieved, running quant calculations"
        elif state.chunks and state.calculations and not state.final_memo:
            next_agent = "auditor_synthesizer"
            reasoning = "Calculations done, running auditor synthesis"
        elif state.final_memo:
            next_agent = "done"
            reasoning = "Final memo generated, finishing job"
        else:
            # Fallback to LLM-based routing
            prompt = ORCHESTRATOR_PROMPT
            await budget_mgr.consume(self.agent_id, prompt)

            resp = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            try:
                data = json.loads(resp.text)
            except Exception:
                clean_text = resp.text.strip().strip('```json').strip('```').strip()
                data = json.loads(clean_text)
            
            next_agent = data.get("next_agent", "done")
            reasoning = data.get("reasoning", "LLM decided")

        state.turn += 1
        state.add_event(self.agent_id, "ROUTING_DECISION", {"next_agent": next_agent, "reasoning": reasoning})
        return next_agent
