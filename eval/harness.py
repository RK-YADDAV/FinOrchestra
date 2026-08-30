import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from eval.scorers import (
    score_math_accuracy, score_citation_accuracy,
    score_false_premise, score_tool_efficiency,
    compute_composite_score
)
from eval.adversarial import detect_injection
from core.context import SharedState
from core.streaming import run_pipeline_async
from db.session import get_isolated_engine

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"

class EvaluationHarness:
    def __init__(self):
        self.test_cases = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))

    async def run_all(self, failed_case_ids: list = None) -> dict:
        cases = self.test_cases
        if failed_case_ids:
            cases = [c for c in cases if c["id"] in failed_case_ids]

        run_id = str(uuid.uuid4())
        results = []

        for tc in cases:
            print(f"Running test case: {tc['id']} - {tc['query']}")
            res = await self._run_single(tc, run_id)
            results.append(res)
            print(f"  Score: {res['composite_score']} | Math: {res['math_accuracy']} | Premise: {res['premise_rejection']}")
            print("Sleeping 60 seconds to avoid Google Gemini free-tier 15 RPM rate limits...")
            await asyncio.sleep(60.0)

        total_score = sum(r["composite_score"] for r in results) / max(len(results), 1)
        await self._persist_run(run_id, total_score, results)
        
        print(f"\n--- EVALUATION COMPLETE ---")
        print(f"Run ID: {run_id}")
        print(f"Total Composite Score: {total_score:.4f} / 1.0000")
        return {"run_id": run_id, "total_score": round(total_score, 4), "results": results}

    async def _run_single(self, tc: dict, run_id: str) -> dict:
        # 1. Adversarial Injection Check (Layer 1)
        if tc.get("adversarial_type") == "prompt_injection":
            injection = detect_injection(tc["query"])
            final_memo = "REJECTED: prompt injection detected." if injection.is_injection else tc["query"]
            state = SharedState(query=tc["query"])
            s_math, j_math = (1.0, "Injection rejection PASSED") if injection.is_injection else (0.0, "FAILED")
            s_cite, j_cite = 1.0, "N/A"
            s_prem, j_prem = 1.0, "N/A"
            s_tool, j_tool = 1.0, "N/A"
        else:
            # Run the multi-agent pipeline!
            try:
                state = await run_pipeline_async(query=tc["query"], job_id=str(uuid.uuid4()))
            except Exception as e:
                import traceback
                print(f"\\n[!] PIPELINE CRASHED ON {tc['id']}: {e}")
                traceback.print_exc()
                state = SharedState(query=tc["query"])
                state.final_memo = f"PIPELINE CRASHED: {e}"
            
            final_memo = state.final_memo or ""

            s_math, j_math = score_math_accuracy(final_memo, tc.get("ground_truth"), tc.get("key_facts"))
            s_cite, j_cite = score_citation_accuracy(state)
            s_prem, j_prem = score_false_premise(state)
            s_tool, j_tool = score_tool_efficiency(state, tc.get("expected_min_tool_calls", 1), tc.get("expected_max_tool_calls", 5))

        scores = {
            "math_accuracy": s_math,
            "citation_accuracy": s_cite,
            "premise_rejection": s_prem,
            "tool_efficiency": s_tool,
        }
        composite = compute_composite_score(scores)

        return {
            "run_id": run_id,
            "test_case_id": tc["id"],
            "category": tc["category"],
            "final_memo": final_memo[:2000],
            "composite_score": composite,
            **scores,
            "justifications": {
                "math_accuracy": j_math, "citation_accuracy": j_cite,
                "premise_rejection": j_prem, "tool_efficiency": j_tool,
            }
        }

    async def _persist_run(self, run_id: str, total_score: float, results: list) -> None:
        from sqlalchemy import text
        engine = get_isolated_engine()
        async with engine.begin() as db:
            for r in results:
                await db.execute(text("""
                    INSERT INTO eval_results
                    (run_id, test_case_id, category, math_accuracy, citation_accuracy,
                     premise_rejection, tool_efficiency, justifications, final_memo)
                    VALUES (:rid, :tcid, :cat, :ma, :ca, :pr, :te, CAST(:j AS jsonb), :fa)
                """), {
                    "rid": run_id, "tcid": r["test_case_id"], "cat": r["category"],
                    "ma": r["math_accuracy"], "ca": r["citation_accuracy"],
                    "pr": r["premise_rejection"], "te": r["tool_efficiency"],
                    "j": json.dumps(r["justifications"]), "fa": r["final_memo"],
                })
        await engine.dispose()

if __name__ == "__main__":
    harness = EvaluationHarness()
    asyncio.run(harness.run_all())
