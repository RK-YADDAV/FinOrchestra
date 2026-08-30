from __future__ import annotations
import asyncio
import hashlib
import json
import time
from enum import Enum
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from core.context import SharedState


class ToolResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    numerical_output: Optional[float] = None
    error_code: Optional[str] = None  # TIMEOUT | NO_RESULTS | MATH_ERROR | SECURITY_VIOLATION | INVALID_INPUT | EXEC_ERROR
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    tool_name: str = ""


class ToolAction(str, Enum):
    RETRY_SAME         = "retry_same"         # TIMEOUT: transient network delay, retry same input
    RETRY_REFORMULATE  = "retry_reformulate"  # NO_RESULTS: mutate NSE/BSE symbol or broaden query
    RECALCULATE        = "recalculate"        # MATH_ERROR: zero division / NaN -> constrain parameters
    SKIP_LOG           = "skip_log"           # SECURITY_VIOLATION: blocked import / illegal SQL -> log & skip
    FALLBACK           = "fallback"           # Fatal error -> fallback to session memory
    ABORT              = "abort"              # Retries exhausted (max 3 attempts)


def handle_tool_failure(
    result: ToolResult,
    tool_name: str,
    attempt: int,
    state: SharedState,
) -> ToolAction:
    """100% deterministic Python failure dispatch. Stays in code, never in prompts."""
    if result.error_code == "TIMEOUT":
        return ToolAction.RETRY_SAME if attempt < 2 else ToolAction.ABORT

    elif result.error_code in ("NO_RESULTS", "INVALID_TICKER"):
        return ToolAction.RETRY_REFORMULATE if attempt < 2 else ToolAction.ABORT

    elif result.error_code == "MATH_ERROR":
        return ToolAction.RECALCULATE if attempt < 2 else ToolAction.ABORT

    elif result.error_code in ("INVALID_INPUT", "SECURITY_VIOLATION"):
        state.add_event("quant_runner", "POLICY_VIOLATION", {
            "violation_type": "security_or_schema_violation",
            "details": f"Tool '{tool_name}' blocked: {result.error_message}"
        })
        return ToolAction.SKIP_LOG  # Never retry security violations

    elif result.error_code == "EXEC_ERROR":
        return ToolAction.FALLBACK if attempt < 2 else ToolAction.ABORT

    return ToolAction.ABORT


async def tool_nse_bse_quote(ticker: str, redis_client=None) -> ToolResult:
    start = time.monotonic()
    clean_ticker = ticker.strip().upper().replace(".NS", "").replace(".BO", "").replace("-", "")

    if not clean_ticker or len(clean_ticker) > 15:
        return ToolResult(success=False, error_code="INVALID_INPUT", error_message=f"Invalid ticker: '{ticker}'", tool_name="nse_bse_quote")

    # 1. Check Redis Cache
    if redis_client:
        cached = await redis_client.get(f"nse_quote:{clean_ticker}")
        if cached:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            return ToolResult(success=True, data=json.loads(cached), tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)

    try:
        await asyncio.sleep(0.05)  # Simulate network latency
        # Sample Indian equity data (production: calls NSEpy / YFinance / Tickertape API)
        indian_market_data = {
            "RELIANCE": {"cmp": 2980.50, "market_cap_cr": 2016500, "pe": 28.4, "promoter_pledge_pct": 0.0, "high_52w": 3217.90, "low_52w": 2220.30},
            "TCS": {"cmp": 4150.00, "market_cap_cr": 1502300, "pe": 32.1, "promoter_pledge_pct": 0.0, "high_52w": 4585.00, "low_52w": 3313.00},
            "TATAMOTORS": {"cmp": 985.20, "market_cap_cr": 362400, "pe": 16.8, "promoter_pledge_pct": 1.2, "high_52w": 1179.00, "low_52w": 593.50},
            "HDFCBANK": {"cmp": 1640.00, "market_cap_cr": 1248000, "pe": 19.2, "promoter_pledge_pct": 0.0, "high_52w": 1794.00, "low_52w": 1363.55},
            "ITC": {"cmp": 485.00, "market_cap_cr": 605000, "pe": 29.5, "promoter_pledge_pct": 0.0, "high_52w": 528.50, "low_52w": 399.30},
        }

        if clean_ticker not in indian_market_data:
            return ToolResult(success=False, error_code="NO_RESULTS", error_message=f"Ticker '{ticker}' not found in NSE/BSE registry", tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)

        data = indian_market_data[clean_ticker]
        if redis_client:
            await redis_client.setex(f"nse_quote:{clean_ticker}", 300, json.dumps(data))

        return ToolResult(success=True, data=data, tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)

    except asyncio.TimeoutError:
        return ToolResult(success=False, error_code="TIMEOUT", error_message="NSE quote request timed out", tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)


def broaden_market_query(kwargs: dict, error_code: str, attempt: int) -> dict:
    if error_code == "NO_RESULTS" and "ticker" in kwargs:
        t = kwargs["ticker"]
        kwargs["ticker"] = t.replace(".", "").replace("-", "").split()[0]
    return kwargs


BLOCKED_PATTERNS = [
    "import os", "import sys", "import subprocess", "open(",
    "importlib", "pathlib", "socket", "urllib", "requests",
    "__builtins__", "__import__", "exec(", "eval("
]

async def tool_quant_math_sandbox(code: str, timeout_seconds: float = 10.0) -> ToolResult:
    start = time.monotonic()
    if not code or not code.strip():
        return ToolResult(success=False, error_code="INVALID_INPUT", error_message="Code cannot be empty", tool_name="quant_math_sandbox")

    for pattern in BLOCKED_PATTERNS:
        if pattern in code:
            return ToolResult(success=False, error_code="SECURITY_VIOLATION", error_message=f"Forbidden pattern detected: '{pattern}'", tool_name="quant_math_sandbox")

    try:
        import sys
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        latency = (time.monotonic() - start) * 1000
        stdout = stdout_b.decode("utf-8", errors="replace").strip()
        stderr = stderr_b.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            err_code = "MATH_ERROR" if any(k in stderr for k in ["ZeroDivisionError", "ValueError", "OverflowError"]) else "EXEC_ERROR"
            return ToolResult(success=False, error_code=err_code, error_message=f"Exit code {proc.returncode}: {stderr}", data={"stdout": stdout, "stderr": stderr}, tool_name="quant_math_sandbox", latency_ms=latency)

        num_val = None
        for line in reversed(stdout.splitlines()):
            try:
                num_val = float(line.replace("₹", "").replace("Cr", "").replace(",", "").replace("%", "").strip())
                break
            except ValueError:
                continue

        return ToolResult(success=True, data={"stdout": stdout, "stderr": stderr, "exit_code": 0}, numerical_output=num_val, tool_name="quant_math_sandbox", latency_ms=latency)

    except asyncio.TimeoutError:
        return ToolResult(success=False, error_code="TIMEOUT", error_message=f"Exceeded timeout of {timeout_seconds}s", tool_name="quant_math_sandbox", latency_ms=(time.monotonic() - start) * 1000)


async def tool_filings_rag(query: str, ticker: Optional[str], db_engine, embed_client, limit: int = 5) -> ToolResult:
    start = time.monotonic()
    from sqlalchemy import text

    # Generate 768-dim query embedding
    try:
        emb_resp = await asyncio.to_thread(
            embed_client.models.embed_content,
            model="gemini-embedding-001", 
            contents=query
        )
        # Handle the returned structure properly for new genai sdk
        query_vector = emb_resp.embeddings[0].values[:768]
        emb_str = "[" + ",".join(str(x) for x in query_vector) + "]"
    except Exception as e:
        return ToolResult(success=False, error_code="EXEC_ERROR", error_message=f"Embedding failed: {e}", tool_name="filings_rag", latency_ms=(time.monotonic() - start) * 1000)

    sql = """
        SELECT id, company, ticker, fiscal_year, doc_type, content,
               1 - (embedding <=> :emb::vector(768)) AS relevance
        FROM annual_report_chunks
        ORDER BY embedding <=> :emb::vector(768)
        LIMIT :limit
    """

    try:
        async with db_engine.connect() as conn:
            rows = await conn.execute(text(sql), {"emb": emb_str, "limit": limit})
            results = rows.mappings().all()

        if not results:
            return ToolResult(success=False, error_code="NO_RESULTS", error_message="No matching chunks found in knowledge base", tool_name="filings_rag", latency_ms=(time.monotonic() - start) * 1000)

        chunks_data = [
            {
                "id": str(r["id"]), "company": r["company"], "ticker": r["ticker"],
                "doc_type": r["doc_type"], "text": r["content"], "relevance": float(r["relevance"])
            }
            for r in results
        ]
        return ToolResult(success=True, data={"chunks": chunks_data}, tool_name="filings_rag", latency_ms=(time.monotonic() - start) * 1000)

    except Exception as e:
        return ToolResult(success=False, error_code="EXEC_ERROR", error_message=str(e), tool_name="filings_rag", latency_ms=(time.monotonic() - start) * 1000)


SCHEMA_DESCRIPTION = """
PostgreSQL Tables (READ-ONLY, SELECT only):
- standalone_financials(ticker TEXT, fiscal_year INT, revenue_cr NUMERIC, ebitda_cr NUMERIC, pat_cr NUMERIC, total_assets_cr NUMERIC, net_worth_cr NUMERIC, total_debt_cr NUMERIC)
- consolidated_financials(ticker TEXT, fiscal_year INT, revenue_cr NUMERIC, ebitda_cr NUMERIC, pat_cr NUMERIC, total_assets_cr NUMERIC, net_worth_cr NUMERIC, total_debt_cr NUMERIC)
- shareholding_patterns(ticker TEXT, quarter TEXT, promoter_pct NUMERIC, promoter_pledge_pct NUMERIC, fii_pct NUMERIC, dii_pct NUMERIC, public_pct NUMERIC)
"""

async def tool_indian_sql(nl_query: str, db_engine, llm_client) -> ToolResult:
    start = time.monotonic()
    if not nl_query or not nl_query.strip():
        return ToolResult(success=False, error_code="INVALID_INPUT", error_message="Query cannot be empty", tool_name="indian_sql")

    prompt = f"Convert to PostgreSQL SQL (SELECT only):\nSchema: {SCHEMA_DESCRIPTION}\nQuery: {nl_query}\nReturn ONLY the SQL string without markdown blocks or explanation."
    try:
        resp = await llm_client.models.generate_content(
            model="gemini-3.6-flash", 
            contents=prompt
        )
        sql = resp.text.strip().strip("```sql").strip("```").strip()

        if not sql.upper().startswith("SELECT"):
            return ToolResult(success=False, error_code="INVALID_INPUT", error_message="Generated SQL must be a SELECT statement", data={"sql": sql}, tool_name="indian_sql", latency_ms=(time.monotonic() - start) * 1000)

        from sqlalchemy import text
        async with db_engine.connect() as conn:
            result = await conn.execute(text(sql))
            rows = result.mappings().all()

        if not rows:
            return ToolResult(success=False, error_code="NO_RESULTS", error_message="Query returned 0 rows", data={"sql": sql}, tool_name="indian_sql", latency_ms=(time.monotonic() - start) * 1000)

        return ToolResult(success=True, data={"rows": [dict(r) for r in rows[:50]], "sql": sql, "count": len(rows)}, tool_name="indian_sql", latency_ms=(time.monotonic() - start) * 1000)

    except Exception as e:
        return ToolResult(success=False, error_code="EXEC_ERROR", error_message=str(e), tool_name="indian_sql", latency_ms=(time.monotonic() - start) * 1000)


async def execute_tool_with_retry(
    tool_fn: Callable,
    tool_name: str,
    agent_id: str,
    state: SharedState,
    tool_kwargs: Dict[str, Any],
    modify_input_fn: Optional[Callable] = None,
    max_retries: int = 2,
) -> ToolResult:
    current_kwargs = dict(tool_kwargs)
    result = None

    for attempt in range(1, max_retries + 2):
        s = time.monotonic()
        
        # Determine if tool requires await
        import inspect
        if inspect.iscoroutinefunction(tool_fn):
            result = await tool_fn(**current_kwargs)
        else:
            result = tool_fn(**current_kwargs)
            
        latency = (time.monotonic() - s) * 1000

        tool_record = {
            "job_id": state.job_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "attempt_number": min(attempt, 3),
            "input_data": dict(current_kwargs),
            "output_data": result.data,
            "numerical_output": result.numerical_output,
            "latency_ms": latency,
            "accepted": result.success,
            "error_code": result.error_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
        state.tool_calls.append(tool_record)

        if result.success:
            # RoMA ParseData: Sanitize indirect prompt injections
            out_str = json.dumps(result.data or {})
            if any(p in out_str.lower() for p in ["ignore previous instructions", "system prompt", "jailbreak"]):
                state.add_event("quant_runner", "INJECTION_DETECTED", {
                    "tool": tool_name, "details": "Indirect prompt injection detected in tool output."
                })
                return ToolResult(success=False, error_code="SECURITY_VIOLATION", error_message="Injection detected in tool output", tool_name=tool_name, latency_ms=latency)
            return result

        action = handle_tool_failure(result, tool_name, attempt, state)
        if action in (ToolAction.SKIP_LOG, ToolAction.ABORT) or attempt >= max_retries + 1:
            return result

        if modify_input_fn:
            current_kwargs = modify_input_fn(current_kwargs, result.error_code, attempt)

        await asyncio.sleep(0.5 * attempt)

    return result
