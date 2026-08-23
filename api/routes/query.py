import json
import uuid
import os
import asyncio
import redis.asyncio as aioredis
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from eval.adversarial import detect_injection
from core.streaming import run_pipeline_async

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    company: str = ""
    ticker: str = ""

@router.post("/v1/query")
async def submit_query(request: Request, body: QueryRequest):
    # 1. Layer 1 Prompt Injection Defense
    injection = detect_injection(body.query)
    if injection.is_injection:
        raise HTTPException(status_code=400, detail={"error": "INJECTION_DETECTED", "pattern": injection.detected_pattern})

    job_id = str(uuid.uuid4())
    print(f"[{job_id}] Accepted request.")
    
    from core.streaming import RedisPublisher
    q = RedisPublisher.get_queue(job_id)

    # 2. Launch async task in background
    asyncio.create_task(run_pipeline_async(query=body.query, company=body.company, ticker=body.ticker, job_id=job_id))
    print(f"[{job_id}] Background task launched.")

    # 3. Stream events to client
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                # Wait for the next message from the queue
                try:
                    message = await asyncio.wait_for(q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                if message.get("type") != "message":
                    continue
                data = message.get("data", "{}")
                yield f"data: {data}\n\n"
                
                parsed = json.loads(data)
                if parsed.get("event_type") in ("done", "error"):
                    break
        finally:
            if job_id in RedisPublisher.queues:
                del RedisPublisher.queues[job_id]

    return EventSourceResponse(event_generator())
