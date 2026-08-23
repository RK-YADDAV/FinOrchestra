import json
import asyncio
from core.context import SharedState, CalculationResult
from core.budget import ContextBudgetManager
from core.tools import execute_tool_with_retry, tool_quant_math_sandbox
from agents.base import BaseAgent

QUANT_PROMPT = """You are the Quant ToolRunner for Indian Equities.
Generate deterministic Python scripts to calculate exact financial ratios in \u20b9 Crores.

Query: {query}
Financial Data: {retrieved_data}

Standard Formulas:
- ROCE = (EBIT / (Total Assets - Current Liabilities)) * 100
- Debt-to-Equity = Total Debt / Total Shareholders' Equity
- Operating Cash Flow Ratio = Cash from Operations / Current Liabilities

Return ONLY executable Python code inside ```python ... ``` blocks."""

class QuantRunnerAgent(BaseAgent):
    def __init__(self):
        super().__init__("quant_runner")

    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        chunks_text = "\n\n".join([f"[{c.source_tag}] {c.text}" for c in state.chunks])
        prompt = QUANT_PROMPT.format(query=state.query, retrieved_data=chunks_text)
        
        await budget_mgr.consume(self.agent_id, prompt)
        resp = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Extract python code
        text = resp.text
        code = ""
        if "```python" in text:
            code = text.split("```python")[1].split("```")[0].strip()
        elif "```" in text:
            code = text.split("```")[1].strip()
        else:
            code = text.strip()

        if not code:
            state.add_event(self.agent_id, "QUANT_FAILED", {"error": "No python code generated"})
            return

        res = await execute_tool_with_retry(
            tool_fn=tool_quant_math_sandbox,
            tool_name="tool_quant_math_sandbox",
            agent_id=self.agent_id,
            state=state,
            tool_kwargs={"code": code, "timeout_seconds": 10.0},
            max_retries=2
        )

        if res.success and res.data:
            calc_res = CalculationResult(
                metric="Unknown Metric", # LLM should technically output this, stubbing for now
                formula="See Code",
                inputs={},
                output_value=res.numerical_output or 0.0,
                python_code=code,
                stdout=res.data.get("stdout", "")
            )
            state.calculations["quant_run_1"] = calc_res
            state.add_event(self.agent_id, "QUANT_DONE", {"stdout": calc_res.stdout})
        else:
            state.add_event(self.agent_id, "QUANT_FAILED", {"error": res.error_message})
