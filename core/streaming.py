import asyncio
import json
import uuid
import os
import redis.asyncio as aioredis
from typing import Optional
from core.context import SharedState
from core.budget import ContextBudgetManager


class RedisPublisher:
    queues = {}

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url

    async def connect(self):
        pass

    @classmethod
    def get_queue(cls, job_id: str) -> asyncio.Queue:
        if job_id not in cls.queues:
            cls.queues[job_id] = asyncio.Queue()
        return cls.queues[job_id]

    async def publish(self, job_id: str, event_data: dict):
        q = self.get_queue(job_id)
        await q.put({"type": "message", "data": json.dumps(event_data)})

    async def publish_done(self, job_id: str, final_memo: str, provenance: list):
        await self.publish(job_id, {
            "event_type": "done", "job_id": job_id,
            "final_memo": final_memo, "provenance": [p.model_dump() for p in provenance]
        })

    async def publish_error(self, job_id: str, error_msg: str):
        await self.publish(job_id, {"event_type": "error", "error": error_msg})

    async def disconnect(self):
        pass


async def run_pipeline_async(query: str, company: Optional[str] = None, ticker: Optional[str] = None, job_id: Optional[str] = None) -> SharedState:
    print(f"[{job_id}] Starting run_pipeline_async...")
    state = SharedState(job_id=job_id or str(uuid.uuid4()), query=query, company=company, ticker=ticker)
    redis_pub = RedisPublisher()
    print(f"[{job_id}] Connecting RedisPublisher...")
    await redis_pub.connect()
    print(f"[{job_id}] RedisPublisher connected.")
    
    try:
        budget_mgr = ContextBudgetManager(state, redis_pub)

        from agents.orchestrator import OrchestratorAgent
        from agents.decomposition import DecompositionAgent
        from agents.retrieval import IndianFilingRetrievalAgent
        from agents.quant_runner import QuantToolRunnerAgent
        from agents.auditor_synthesizer import AuditorSynthesizerAgent

        agents = {
            "orchestrator": OrchestratorAgent(),
            "decomposition": DecompositionAgent(),
            "retrieval": IndianFilingRetrievalAgent(),
            "quant_runner": QuantToolRunnerAgent(),
            "auditor_synthesizer": AuditorSynthesizerAgent(),
        }

        last_published_event = 0

        async def publish_new_events():
            nonlocal last_published_event
            while last_published_event < len(state.events):
                ev = state.events[last_published_event]
                await redis_pub.publish(state.job_id, {
                    "event_type": "step",
                    "step_data": ev
                })
                last_published_event += 1

        while not state.is_done():
            # 1. Orchestrator routes
            await agents["orchestrator"].run(state, budget_mgr, redis_pub)
            await publish_new_events()
            next_agent = state.events[-1]["details"].get("next_agent", "auditor_synthesizer")

            if next_agent == "done" or state.is_done():
                break

            # 2. Execute selected agent
            agent = agents.get(next_agent)
            if agent:
                budget_mgr.assert_compliant(next_agent)
                await agent.run(state, budget_mgr, redis_pub)
                await publish_new_events()

            # Prevent infinite loops if state.turn gets modified weirdly
            if state.turn >= 10:
                break

        state.status = "done"
        state.clean_final_memo()
        await redis_pub.publish_done(state.job_id, state.final_memo, state.provenance)
        return state
    except Exception as e:
        import traceback
        err_msg = f"{str(e)}\n\n{traceback.format_exc()}"
        state.status = "failed"
        await redis_pub.publish_error(state.job_id, err_msg)
        raise
    finally:
        await redis_pub.disconnect()
