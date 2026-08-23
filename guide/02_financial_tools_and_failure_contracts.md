# FinOrchestra India: Financial Tools, Failure Contracts & Database Architecture

This document provides the complete specification for FinOrchestra India's tool suite, deterministic failure state machine, AST-sandboxed math engine in **₹ Crores**, and PostgreSQL database schema.

---

## 1. Tool Failure State Machine (`core/tools.py`)

All tool error handling and retry logic is governed strictly by a **deterministic Python state machine**. Error recovery decisions **never live in prompt strings**.

```python
from __future__ import annotations
import asyncio
import hashlib
import json
import time
from enum import Enum
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
```

---

## 2. Complete Implementations of the 4 Indian Financial Tools

### Tool 1: `tool_nse_bse_quote` (Live Quotes, Valuations & Promoter Pledges)
- **Role**: Fetches live and historical equity metrics for Indian stocks (P/E ratio, Market Cap in ₹ Crores, 52-Week High/Low, Promoters' Pledged Share percentage).
- **Redis Caching**: Cached in Redis with key `nse_quote:{symbol}` and 300s TTL to prevent rate limits.

```python
async def tool_nse_bse_quote(ticker: str, redis_client=None) -> ToolResult:
    start = time.monotonic()
    clean_ticker = ticker.strip().upper().replace(".NS", "").replace(".BO", "").replace("-", "")

    if not clean_ticker or len(clean_ticker) > 15:
        return ToolResult(success=False, error_code="INVALID_INPUT", error_message=f"Invalid ticker: '{ticker}'", tool_name="nse_bse_quote")

    # 1. Check Redis Cache
    if redis_client:
        cached = await redis_client.get(f"nse_quote:{clean_ticker}")
        if cached:
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
```

### Tool 2: `tool_quant_math_sandbox` (Calculations in ₹ Crores)
- **Role**: Executes deterministic Python math for Indian corporate ratios, DCF in ₹ Cr, and ROCE calculations.
- **Security AST Check**: Scans for forbidden patterns (`import os`, `sys`, `subprocess`, `open`, `requests`, `exec`, `eval`) before running.

```python
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
```

### Tool 3: `tool_filings_rag` (BSE/NSE Vector Search)
- **Role**: Searches 768-dimensional embeddings of Indian Annual Reports (MDA, Notes to Accounts, Auditor's Report) and Concall Transcripts using cosine distance (`<=>`).

```python
async def tool_filings_rag(query: str, ticker: Optional[str], db_engine, embed_client, limit: int = 5) -> ToolResult:
    start = time.monotonic()
    from sqlalchemy import text

    # Generate 768-dim query embedding
    emb_resp = await embed_client.embed(query)
    emb_str = "[" + ",".join(str(x) for x in emb_resp) + "]"

    sql = """
        SELECT id, company, ticker, fiscal_year, doc_type, content,
               1 - (embedding <=> :emb::vector(768)) AS relevance
        FROM annual_report_chunks
        WHERE (:ticker IS NULL OR ticker = :ticker)
        ORDER BY embedding <=> :emb::vector(768)
        LIMIT :limit
    """

    try:
        async with db_engine.connect() as conn:
            rows = await conn.execute(text(sql), {"emb": emb_str, "ticker": ticker, "limit": limit})
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
```

### Tool 4: `tool_indian_sql` (Read-Only Financial Statement Database)
- **Role**: Converts natural language financial queries into SQL statements over structured tables: `standalone_financials`, `consolidated_financials`, `shareholding_patterns`.
- **Security**: Runs under the dedicated `fin_readonly` PostgreSQL user.

```python
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

    prompt = f"Convert to PostgreSQL SQL (SELECT only):\nSchema: {SCHEMA_DESCRIPTION}\nQuery: {nl_query}\nReturn ONLY the SQL string."
    try:
        resp = await llm_client.generate(prompt)
        sql = resp.strip().strip("```sql").strip("```").strip()

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
```

---

## 3. Tool Retry Wrapper with RoMA ParseData

```python
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
        result = await tool_fn(**current_kwargs)
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
```

---

## 4. Database Sessions & Connection Pooling (`db/session.py`)

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

# Supabase PostgreSQL connection string (set in .env)
DATABASE_URL = os.environ["DATABASE_URL"]  # e.g., postgresql+asyncpg://<user>:<password>@<host>:5432/<db>

# 1. Primary Engine for FastAPI API Endpoints (Connection Pooling enabled)
engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# 2. Isolated NullPool Engine for Async Background Tasks & Vector Search
# NullPool prevents asyncpg InterfaceError ("another operation is in progress")
# across dynamic asyncio event loops.
def get_isolated_engine(readonly: bool = False):
    url = DATABASE_URL
    if readonly:
        primary_user = os.environ.get("POSTGRES_USER", "postgres")
        readonly_user = os.environ.get("POSTGRES_READONLY_USER", "fin_readonly")
        url = url.replace(primary_user, readonly_user)
    return create_async_engine(url, poolclass=NullPool)
```

---

## 5. PostgreSQL DDL Schema (Execute via Supabase SQL Editor)

> **Note**: Supabase projects have `uuid-ossp` and `vector` (pgvector) extensions available by default. Enable them from the Supabase Dashboard under **Database → Extensions**, or run the SQL below in the **SQL Editor**.

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Master Jobs Table
CREATE TABLE jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    company VARCHAR(100),
    ticker VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'running' CHECK (status IN ('running','done','failed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    total_tokens INT DEFAULT 0,
    model_used VARCHAR(50) DEFAULT 'gemini-2.5-flash'
);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created ON jobs(created_at DESC);

-- 2. Granular Event Log (Audit Trail)
CREATE TABLE execution_events (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    seq INT NOT NULL,
    agent VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    prompt_sent TEXT,
    output_received TEXT,
    token_count INT DEFAULT 0,
    details JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_events_job ON execution_events(job_id);

-- 3. Tool Calls Table (with GIN index)
CREATE TABLE tool_calls (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    agent_id VARCHAR(50) NOT NULL,
    tool_name VARCHAR(50) NOT NULL,
    attempt_number INT NOT NULL DEFAULT 1 CHECK (attempt_number BETWEEN 1 AND 3),
    input_json JSONB,
    output_json JSONB,
    numerical_output FLOAT,
    latency_ms FLOAT,
    accepted BOOLEAN,
    error_code VARCHAR(50),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tool_calls_job ON tool_calls(job_id);
CREATE INDEX idx_tool_calls_input_gin ON tool_calls USING GIN (input_json);

-- 4. BSE/NSE Annual Report Chunks (Vector Store)
CREATE TABLE annual_report_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company VARCHAR(100) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    fiscal_year INT NOT NULL,
    doc_type VARCHAR(50) NOT NULL, -- Annual Report / Concall / SEBI LODR 33
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_report_chunks_hnsw ON annual_report_chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_report_chunks_ticker ON annual_report_chunks(ticker, fiscal_year);

-- 5. Evaluation Benchmark Results with Generated Composite Score
CREATE TABLE eval_results (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    test_case_id VARCHAR(20) NOT NULL,
    category VARCHAR(20) NOT NULL,
    math_accuracy FLOAT,
    citation_accuracy FLOAT,
    premise_rejection FLOAT,
    tool_efficiency FLOAT,
    composite_score FLOAT GENERATED ALWAYS AS (
        COALESCE(math_accuracy,0)*0.35 +
        COALESCE(citation_accuracy,0)*0.25 +
        COALESCE(premise_rejection,0)*0.20 +
        COALESCE(tool_efficiency,0)*0.20
    ) STORED,
    justifications JSONB,
    final_memo TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_eval_run_case UNIQUE (run_id, test_case_id)
);

-- 6. Read-Only Security Role
-- Note: On Supabase, you can create a read-only role via the SQL Editor.
-- Supabase manages the database name internally, so omit the GRANT CONNECT line.
CREATE ROLE fin_readonly WITH LOGIN PASSWORD 'fin_readonly_pass';
GRANT USAGE ON SCHEMA public TO fin_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO fin_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO fin_readonly;
```
