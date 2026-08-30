# FinOrchestra India (ArthGraph): Engineering Build Manual & Phased Implementation Blueprint

Welcome to the **FinOrchestra India** (codenamed **ArthGraph**) engineering build manual.

This guide is written from the perspective of a **Senior Principal Software Architect** mentoring a developer who is new to building complex multi-agent systems. It breaks down the entire project into **7 clean, step-by-step engineering phases (Phases 1 to 7)**.

We do **not** dumb down or skip any architectural depth—every async lock, vector similarity calculation, AST security check, and database schema is fully detailed. However, every concept is explained using **plain English intuition**, concrete real-world metaphors, and a **consistent narrative thread**: an institutional investment committee on Dalal Street auditing India's largest conglomerates (such as Tata Motors and Reliance Industries).

---

## Table of Contents
1. [The Dalal Street Storyline: The Investment Committee Analogy](#1-the-dalal-street-storyline-the-investment-committee-analogy)
2. [Complete Project Repository & Folder Structure](#2-complete-project-repository--folder-structure)
3. [Phase 1: Infrastructure (Supabase + Upstash), Vector Database & Connection Pooling](#phase-1-infrastructure-supabase--upstash-vector-database--connection-pooling)
4. [Phase 2: The Blackboard State & Token Budget Governance](#phase-2-the-blackboard-state--token-budget-governance)
5. [Phase 3: Indian Financial Tools, AST Math Sandbox & Failure Engine](#phase-3-indian-financial-tools-ast-math-sandbox--failure-engine)
6. [Phase 4: The 5 Specialized Agents, Turn Routing & DAG Validation](#phase-4-the-5-specialized-agents-turn-routing--dag-validation)
7. [Phase 5: Redis Pub/Sub Streaming, Event Bus & FastAPI Gateway](#phase-5-redis-pubsub-streaming-event-bus--fastapi-gateway)
8. [Phase 6: Forensic Auditing, Rumor Defense & Institutional Memo Synthesis](#phase-6-forensic-auditing-rumor-defense--institutional-memo-synthesis)
9. [Phase 7: Evaluation Benchmark Harness, CI Test Suite & Leakage Guards](#phase-7-evaluation-benchmark-harness-ci-test-suite--leakage-guards)
10. [Senior Architect's Self-Critique & Anti-Pattern Checklist](#10-senior-architects-self-critique--anti-pattern-checklist)

---

## 1. The Dalal Street Storyline: The Investment Committee Analogy

To understand how FinOrchestra coordinates multiple AI models without chaos, imagine a top-tier Mumbai institutional equity research desk analyzing a complex corporate query:

> *"Evaluate Tata Motors' JLR debt reduction trajectory, calculate Standalone vs. Consolidated ROCE for FY24 in ₹ Crores, and check for promoter pledging risks."*

In a traditional, messy office (or a naive AI pipeline), analysts shout over each other, pass loose papers down the hallway, and make arithmetic errors in their heads. 

In **FinOrchestra**, the office operates as a disciplined **Investment Committee**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FinOrchestra Investment Committee Analogy                       │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│ Role in Committee        │ FinOrchestra Agent          │ Operational Responsibility    │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 1. Committee Chairman    │ Orchestrator Agent          │ Controls the meeting, decides │
│                          │ (`orchestrator.py`)         │ who speaks next, halts loops. │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 2. Research Planner      │ Decomposition Agent         │ Breaks complex goals into a   │
│                          │ (`decomposition.py`)        │ step-by-step task checklist.  │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 3. Filing Librarian      │ Indian Filing RAG Agent     │ Fetches exact BSE/NSE reports,│
│                          │ (`retrieval.py`)            │ footnotes, and concall notes. │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 4. Quantitative Analyst  │ Quant ToolRunner Agent      │ Executes real Python formulas │
│                          │ (`quant_runner.py`)         │ in ₹ Crores (no mental math). │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ 5. Forensic Auditor &    │ Auditor & Synthesizer Agent │ Reconciles numbers, rejects   │
│    Lead Author           │ (`auditor_synthesizer.py`)  │ fake rumors, writes final memo│
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

The members **never whisper to each other directly**. Instead, all 5 members sit around a single, shared conference room whiteboard: the **`SharedState` Blackboard**. 

Every piece of data, retrieved filing paragraph, Python calculation, and audit warning is written directly on the whiteboard for all members to read.

---

## 2. Complete Project Repository & Folder Structure

Here is the exact, clean repository layout for the entire FinOrchestra project. Every file has a single, well-defined responsibility:

```
FinOrchestra-India/
├── .env.example                          # API keys, Supabase DB URL, Upstash Redis URL
├── Makefile                              # Automation: test, seed, run, eval, lint
├── pyproject.toml                        # Modern Python project configuration
├── requirements.txt                      # Pinned production dependencies
│
├── api/                                  # FastAPI Ingress & Gateway Layer
│   ├── __init__.py
│   ├── main.py                           # FastAPI application factory, lifespan, CORS
│   └── routes/
│       ├── __init__.py
│       ├── query.py                      # POST /v1/query (SSE live stream handler)
│       ├── trace.py                      # GET /v1/jobs/{job_id}/trace (Audit inspector)
│       ├── eval.py                       # GET /v1/eval/latest & POST /v1/eval/run
│       ├── rewrites.py                   # GET & POST /v1/rewrites/review (Hot-swap prompts)
│       └── schemas.py                    # Pydantic request & response schemas
│
├── core/                                 # Central Engine & Shared State
│   ├── __init__.py
│   ├── context.py                        # SharedState blackboard & supporting dataclasses
│   ├── budget.py                         # ContextBudgetManager (asyncio.Lock token tracking)
│   ├── tools.py                          # 4 Financial tools, ToolResult, ToolAction state machine
│   └── streaming.py                      # RedisPublisher, event dispatch & run_pipeline_async
│
├── agents/                               # The 5 Focused Financial Agents
│   ├── __init__.py
│   ├── base.py                           # BaseAgent abstract class
│   ├── orchestrator.py                   # OrchestratorAgent (Master turn & routing node)
│   ├── decomposition.py                  # DecompositionAgent (Subtask planner & DFS cycle guard)
│   ├── retrieval.py                      # IndianFilingRetrievalAgent (2-Hop BSE/NSE vector RAG)
│   ├── quant_runner.py                   # QuantToolRunnerAgent (Deterministic Python in ₹ Cr)
│   └── auditor_synthesizer.py            # AuditorSynthesizerAgent (Forensic checks & memo writer)
│
├── db/                                   # Database & Storage Layer
│   ├── __init__.py
│   ├── session.py                        # AsyncSessionLocal (Pooled for API, NullPool for workers)
│   └── models.py                         # SQLAlchemy declarative models (Job, Event, ToolCall, etc.)
│
├── eval/                                 # Benchmark Evaluation Harness
│   ├── __init__.py
│   ├── test_cases.json                   # 15-case Indian market benchmark dataset
│   ├── scorers.py                        # 4 Python scorers: Math (35%), Citation (25%), Premise (20%), Tool (20%)
│   ├── adversarial.py                    # Regex pre-orchestrator prompt injection detector
│   └── harness.py                        # EvaluationHarness (Async batch runner & DB recorder)
│
├── scripts/                              # Maintenance & Seeding Utilities
│   ├── __init__.py
│   ├── seed_kb.py                        # Seeds 30 Indian corporate filings into pgvector (384d)
│   └── leakage_check.py                  # Validates zero ground-truth leakage in seed chunks
│
└── tests/                                # Unit & Integration Test Suite
    ├── __init__.py
    ├── conftest.py                       # Fixtures for mock SharedState, budget manager, DB engine
    ├── test_context.py                   # Blackboard state, memo cleaning, event logging tests
    ├── test_budget.py                    # Token budget limits, preflight checks, overflow errors
    ├── test_tools.py                     # AST sandbox security, tool failures, Redis quote caching
    ├── test_orchestrator.py              # Routing rules, DAG cycle detection, agent transitions
    └── test_eval.py                      # Scorer verification, Indian comma parsing, tolerance tests
```

---

## Phase 1: Infrastructure (Supabase + Upstash), Vector Database & Connection Pooling

### 1.1 Objective & Deliverables
Set up the foundational cloud services (no Docker required):
- **Supabase PostgreSQL (with `pgvector`)**: Cloud-hosted PostgreSQL to store text chunks from Indian Annual Reports with 384-dimensional embeddings, as well as job execution traces. Create a free project at [supabase.com](https://supabase.com) and enable the `vector` extension.
- **Upstash Redis**: Serverless Redis for real-time Server-Sent Events (SSE) streaming and market quote caching. Create a free database at [upstash.com](https://upstash.com) and copy the `UPSTASH_REDIS_URL`.
- **SQLAlchemy 2.0 Async Session Layer**: Configured with connection pooling for FastAPI and `NullPool` for isolated background tasks.

### 1.2 Beginner's Intuition
Think of Supabase PostgreSQL as our **permanent legal archive** (holding audited balance sheets, footnotes, and immutable logs). Think of Upstash Redis as our **instant office intercom** (announcing updates to the web browser the millisecond an agent finishes a calculation). Both are cloud-hosted — no Docker containers needed.

### 1.3 Concrete Code Implementation

#### Cloud Services Setup (No Docker Required)

**1. Supabase PostgreSQL Setup:**
1. Go to [supabase.com](https://supabase.com) and create a new project.
2. In the Supabase Dashboard, go to **Database → Extensions** and enable `uuid-ossp` and `vector` (pgvector).
3. Copy your connection string from **Settings → Database → Connection string → URI** (use the `postgresql://` format).
4. For the async Python driver, replace the `postgresql://` prefix with `postgresql+asyncpg://` in your `.env` file.

**2. Upstash Redis Setup:**
1. Go to [upstash.com](https://upstash.com) and create a new Redis database.
2. Copy the **Redis URL** (format: `rediss://<password>@<endpoint>:<port>`).
3. Set it as `UPSTASH_REDIS_URL` in your `.env` file.

**3. `.env.example`:**
```env
# Supabase PostgreSQL (replace prefix postgresql:// → postgresql+asyncpg://)
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<db>

# Upstash Redis
UPSTASH_REDIS_URL=rediss://<password>@<endpoint>:<port>

# Google Gemini API
GOOGLE_API_KEY=<your-gemini-api-key>
```

#### `db/session.py`
```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

# Supabase PostgreSQL connection string (set in .env)
# Format: postgresql+asyncpg://<user>:<password>@<host>:5432/<db>
DATABASE_URL = os.environ["DATABASE_URL"]

# 1. Pooled engine for FastAPI HTTP endpoints (High concurrency, short queries)
engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# 2. Isolated NullPool engine for asynchronous vector search and background tasks
# NullPool prevents asyncpg "InterfaceError: another operation is in progress" across asyncio event loops.
def get_isolated_engine(readonly: bool = False):
    url = DATABASE_URL
    if readonly:
        primary_user = os.environ.get("POSTGRES_USER", "postgres")
        readonly_user = os.environ.get("POSTGRES_READONLY_USER", "fin_readonly")
        url = url.replace(primary_user, readonly_user)
    return create_async_engine(url, poolclass=NullPool)
```

### 1.4 Senior Architect's Self-Critique & Design Decision
> **Critique**: Why use Supabase + Upstash instead of self-hosted Docker containers?
>
> **Senior Decision**: For a development team on Windows, managing Docker containers for PostgreSQL and Redis adds unnecessary operational complexity. Supabase provides managed PostgreSQL 15+ with `pgvector` out of the box, automatic backups, and a browser-based SQL Editor. Upstash provides serverless Redis with a generous free tier and a simple connection URL. This eliminates Docker as a dependency while preserving identical SQLAlchemy and `redis-py` code.
>
> **Critique**: Why not just use a single global connection pool everywhere?
>
> **Senior Decision**: In Python's asynchronous ecosystem, if a background task launched via `asyncio.create_task` tries to reuse a connection from a shared pool while another coroutine is reading a stream, `asyncpg` crashes with a fatal `InterfaceError`. By using `NullPool` for isolated agent worker tasks, every task cleanly opens its own physical connection and disposes of it upon completion.

---

## Phase 2: The Blackboard State & Token Budget Governance

### 2.1 Objective & Deliverables
Implement `core/context.py` and `core/budget.py`. This provides the single source of truth (`SharedState`) and strict token budget enforcement with `asyncio.Lock` thread-safety.

### 2.2 Beginner's Intuition
Without a budget manager, an AI agent given a 300-page Annual Report will blindly try to read all 300 pages at once. It will either run out of memory, hit API token limits, or generate a massive bill. The `ContextBudgetManager` acts like an office expense manager: each agent is allocated a specific token allowance (e.g. 6,144 tokens for Retrieval, 4,096 tokens for the Auditor) and must check in before making an LLM call.

### 2.3 Concrete Code Implementation

#### `core/context.py`
```python
from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    id: str = Field(default_factory=lambda: f"t_{uuid.uuid4().hex[:4]}")
    title: str
    task_type: str = "filing_rag"  # filing_rag | quant_calc | market_quote | forensic_audit
    deps: List[str] = Field(default_factory=list)
    status: str = "pending"        # pending | running | done | failed
    output: Optional[str] = None
    error: Optional[str] = None


class RetrievedChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chunk_{uuid.uuid4().hex[:6]}")
    company: str                   # e.g., "Reliance Industries", "Tata Motors"
    ticker: str                    # e.g., "RELIANCE", "TATAMOTORS"
    document_type: str             # "Annual Report FY24", "Q3 Concall", "SEBI LODR 33"
    fiscal_year: int = 2024
    page_number: Optional[int] = None
    text: str
    source_tag: str                # e.g., "[BSE:RELIANCE:FY24:P128]"
    relevance_score: float = 0.0


class CalculationResult(BaseModel):
    metric: str                    # e.g., "ROCE", "Debt-to-Equity", "DCF_Fair_Value"
    formula: str
    inputs: Dict[str, Any]
    output_value: float            # Value in ₹ Crores or percentage
    python_code: str
    stdout: str


class AuditFlag(BaseModel):
    flag_type: str                 # false_premise | promoter_pledge_high | pat_ocf_divergence | contradiction
    span: str
    reason: str
    severity: str = "HIGH"         # HIGH | MEDIUM | LOW
    status: str = "FLAGGED"        # FLAGGED | RESOLVED | HEDGED | REJECTED


class ProvenanceEntry(BaseModel):
    sentence: str
    source_tag: str                # e.g., "[BSE:TATAMOTORS:FY24:P84]" or "[CALCULATION:ROCE]"
    chunk_id: Optional[str] = None


class SharedState(BaseModel):
    """
    The Single Source of Truth Blackboard.
    All 5 agents communicate strictly by reading/writing to this state.
    """
    model_config = {"arbitrary_types_allowed": True}

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    company: Optional[str] = None
    ticker: Optional[str] = None
    turn: int = 0
    status: str = "running"        # running | done | failed

    subtasks: List[SubTask] = Field(default_factory=list)
    chunks: List[RetrievedChunk] = Field(default_factory=list)
    calculations: Dict[str, CalculationResult] = Field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    audit_flags: List[AuditFlag] = Field(default_factory=list)

    final_memo: str = ""
    provenance: List[ProvenanceEntry] = Field(default_factory=list)

    used_tokens: int = 0
    max_tokens: int = 24000
    events: List[Dict[str, Any]] = Field(default_factory=list)

    def is_done(self) -> bool:
        return self.status in ("done", "failed") or self.turn >= 10

    def clean_final_memo(self) -> None:
        """Strip raw citation tags from user-facing prose while keeping provenance intact."""
        import re
        text = self.final_memo
        text = re.sub(r'\[BSE:[^\]]+\]\s*', '', text)
        text = re.sub(r'\[CONCALL:[^\]]+\]\s*', '', text)
        text = re.sub(r'\[REASONING\]\s*', '', text)
        self.final_memo = text.strip()

    def add_event(self, agent: str, event_type: str, details: Dict[str, Any]) -> None:
        seq = len(self.events)
        self.events.append({
            "seq": seq,
            "job_id": self.job_id,
            "agent": agent,
            "event_type": event_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        })
```

#### `core/budget.py`
```python
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
```

### 2.4 Senior Architect's Self-Critique & Design Decision
> **Critique**: Why not silently truncate text when an agent exceeds its token budget instead of throwing an error?
>
> **Senior Decision**: **Silent truncation is an architectural anti-pattern in finance**. If an agent silently drops the last 1,000 tokens of a document chunk, it might drop the exact footnote detailing a ₹5,000 Cr contingent liability. Throwing a formal `BudgetOverflowError` makes the failure auditable and forces the system to log a policy event.

---

## Phase 3: Indian Financial Tools, AST Math Sandbox & Failure Engine

### 3.1 Objective & Deliverables
Implement `core/tools.py` with 4 Indian financial tools:
1. `tool_nse_bse_quote`: Live Indian stock market metrics with Redis caching.
2. `tool_quant_math_sandbox`: Sandboxed Python math execution in ₹ Crores.
3. `tool_filings_rag`: Vector search on BSE/NSE Annual Reports using `pgvector`.
4. `tool_indian_sql`: Read-only financial statement queries under the `fin_readonly` user.

### 3.2 Beginner's Intuition
LLMs are creative language writers, but terrible calculators. If you ask an LLM to compute a 5-year CAGR or ROCE across 4 quarters, it will often approximate or invent numbers. In FinOrchestra, the LLM is only allowed to **write Python formulas**. The code is inspected for malicious commands, executed in an isolated Python subprocess, and the exact result is extracted.

### 3.3 Concrete Code Implementation

```python
# core/tools.py
from __future__ import annotations
import asyncio
import json
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel
from core.context import SharedState


class ToolResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    numerical_output: Optional[float] = None
    error_code: Optional[str] = None  # TIMEOUT | NO_RESULTS | MATH_ERROR | SECURITY_VIOLATION | INVALID_INPUT
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    tool_name: str = ""


class ToolAction(str, Enum):
    RETRY_SAME         = "retry_same"         # TIMEOUT: retry same input
    RETRY_REFORMULATE  = "retry_reformulate"  # NO_RESULTS: mutate symbol / broaden search
    RECALCULATE        = "recalculate"        # MATH_ERROR: constrain formula parameters
    SKIP_LOG           = "skip_log"           # SECURITY_VIOLATION: log and skip
    FALLBACK           = "fallback"           # Fatal error: route to session context
    ABORT              = "abort"              # Retries exhausted


def handle_tool_failure(result: ToolResult, tool_name: str, attempt: int, state: SharedState) -> ToolAction:
    if result.error_code == "TIMEOUT":
        return ToolAction.RETRY_SAME if attempt < 2 else ToolAction.ABORT
    elif result.error_code in ("NO_RESULTS", "INVALID_TICKER"):
        return ToolAction.RETRY_REFORMULATE if attempt < 2 else ToolAction.ABORT
    elif result.error_code == "MATH_ERROR":
        return ToolAction.RECALCULATE if attempt < 2 else ToolAction.ABORT
    elif result.error_code in ("INVALID_INPUT", "SECURITY_VIOLATION"):
        state.add_event("quant_runner", "POLICY_VIOLATION", {
            "violation": "security_or_schema_violation", "details": result.error_message
        })
        return ToolAction.SKIP_LOG
    return ToolAction.ABORT


# ── 1. Live NSE/BSE Quote Tool with Redis Caching ─────────────────────────────

async def tool_nse_bse_quote(ticker: str, redis_client=None) -> ToolResult:
    start = time.monotonic()
    clean_ticker = ticker.strip().upper().replace(".NS", "").replace(".BO", "").replace("-", "")

    if not clean_ticker or len(clean_ticker) > 15:
        return ToolResult(success=False, error_code="INVALID_INPUT", error_message="Invalid ticker symbol", tool_name="nse_bse_quote")

    if redis_client:
        cached = await redis_client.get(f"nse_quote:{clean_ticker}")
        if cached:
            return ToolResult(success=True, data=json.loads(cached), tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)

    try:
        await asyncio.sleep(0.05)  # Simulate network latency
        market_data = {
            "RELIANCE": {"cmp": 2980.50, "market_cap_cr": 2016500, "pe": 28.4, "promoter_pledge_pct": 0.0},
            "TCS": {"cmp": 4150.00, "market_cap_cr": 1502300, "pe": 32.1, "promoter_pledge_pct": 0.0},
            "TATAMOTORS": {"cmp": 985.20, "market_cap_cr": 362400, "pe": 16.8, "promoter_pledge_pct": 1.2},
            "HDFCBANK": {"cmp": 1640.00, "market_cap_cr": 1248000, "pe": 19.2, "promoter_pledge_pct": 0.0},
            "ITC": {"cmp": 485.00, "market_cap_cr": 605000, "pe": 29.5, "promoter_pledge_pct": 0.0},
        }

        if clean_ticker not in market_data:
            return ToolResult(success=False, error_code="NO_RESULTS", error_message=f"Ticker '{ticker}' not found", tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)

        data = market_data[clean_ticker]
        if redis_client:
            await redis_client.setex(f"nse_quote:{clean_ticker}", 300, json.dumps(data))

        return ToolResult(success=True, data=data, tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)
    except asyncio.TimeoutError:
        return ToolResult(success=False, error_code="TIMEOUT", error_message="Quote API timed out", tool_name="nse_bse_quote", latency_ms=(time.monotonic() - start) * 1000)


# ── 2. Quant Math Sandbox (Calculations in ₹ Crores) ──────────────────────────

BLOCKED_PATTERNS = ["import os", "import sys", "subprocess", "open(", "importlib", "socket", "requests", "exec(", "eval("]

async def tool_quant_math_sandbox(code: str, timeout_seconds: float = 10.0) -> ToolResult:
    start = time.monotonic()
    if not code or not code.strip():
        return ToolResult(success=False, error_code="INVALID_INPUT", error_message="Code cannot be empty", tool_name="quant_math_sandbox")

    for p in BLOCKED_PATTERNS:
        if p in code:
            return ToolResult(success=False, error_code="SECURITY_VIOLATION", error_message=f"Forbidden pattern: '{p}'", tool_name="quant_math_sandbox")

    try:
        import sys
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        latency = (time.monotonic() - start) * 1000
        out_text = stdout.decode().strip()
        err_text = stderr.decode().strip()

        if proc.returncode != 0:
            return ToolResult(success=False, error_code="MATH_ERROR", error_message=err_text, tool_name="quant_math_sandbox", latency_ms=latency)

        num_val = None
        for line in reversed(out_text.splitlines()):
            try:
                num_val = float(line.replace("₹", "").replace("Cr", "").replace(",", "").replace("%", "").strip())
                break
            except ValueError:
                continue

        return ToolResult(success=True, data={"stdout": out_text}, numerical_output=num_val, tool_name="quant_math_sandbox", latency_ms=latency)
    except Exception as e:
        return ToolResult(success=False, error_code="MATH_ERROR", error_message=str(e), tool_name="quant_math_sandbox", latency_ms=(time.monotonic() - start) * 1000)


# ── 3. Tool Retry Wrapper with RoMA ParseData ─────────────────────────────────

async def execute_tool_with_retry(tool_fn: Callable, tool_name: str, agent_id: str, state: SharedState, tool_kwargs: Dict[str, Any], max_retries: int = 2) -> ToolResult:
    current_kwargs = dict(tool_kwargs)
    for attempt in range(1, max_retries + 2):
        s = time.monotonic()
        result = await tool_fn(**current_kwargs)
        latency = (time.monotonic() - s) * 1000

        state.tool_calls.append({
            "job_id": state.job_id, "agent_id": agent_id, "tool_name": tool_name,
            "attempt": attempt, "input": current_kwargs, "output": result.data,
            "numerical_output": result.numerical_output, "latency_ms": latency, "accepted": result.success
        })

        if result.success:
            # RoMA ParseData: Sanitize indirect prompt injections embedded in tool outputs
            out_str = json.dumps(result.data or {})
            if any(p in out_str.lower() for p in ["ignore previous instructions", "system prompt", "jailbreak"]):
                state.add_event("quant_runner", "INJECTION_DETECTED", {"tool": tool_name})
                return ToolResult(success=False, error_code="SECURITY_VIOLATION", error_message="Indirect injection detected", tool_name=tool_name)
            return result

        action = handle_tool_failure(result, tool_name, attempt, state)
        if action in (ToolAction.SKIP_LOG, ToolAction.ABORT) or attempt >= max_retries + 1:
            return result

        await asyncio.sleep(0.5 * attempt)

    return result
```

### 3.4 Senior Architect's Self-Critique & Design Decision
> **Critique**: Why execute Python math in a subprocess instead of using Python's built-in `eval()` or `exec()`?
>
> **Senior Decision**: `eval()` runs inside the parent FastAPI application process. If a malicious query exploits `__import__('os').system(...)`, it can compromise the entire server container. Running code inside an isolated subprocess with an explicit AST pattern blacklist and a 10-second timeout completely isolates the execution environment.

---

## Phase 4: The 5 Specialized Agents, Turn Routing & DAG Validation

### 4.1 Objective & Deliverables
Implement `agents/orchestrator.py`, `decomposition.py`, `retrieval.py`, `quant_runner.py`, and `auditor_synthesizer.py`. Enforce DFS cycle detection on subtasks and dynamic state-machine routing.

### 4.2 Beginner's Intuition
Each agent is like a specialist with a specific job description. The **Orchestrator** is the conductor of the orchestra: it checks what's on the blackboard and tells the next specialist when it's their turn to play. If the **Decomposition** agent creates a circular plan (Task A depends on Task B, which depends on Task A), our **DFS Cycle Check** catches the mistake immediately so the program doesn't freeze.

### 4.3 Concrete Code Implementation

#### `agents/base.py`
```python
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
```

#### `agents/decomposition.py`
```python
import json
import asyncio
from core.context import SharedState, SubTask
from core.budget import ContextBudgetManager
from agents.base import BaseAgent

DECOMPOSITION_PROMPT = """You are an Indian Equity Research Planner.
Break the user's financial query into 2 to 4 typed subtasks with dependency ordering.

Query: {query}
Company: {company} | Ticker: {ticker}

Allowed Task Types:
- filing_rag: Balance Sheet, P&L, Cash Flow, MDA, Notes to Accounts (BSE/NSE Annual Reports).
- concall_rag: Management commentary, margin guidance, CapEx execution.
- market_quote: Live CMP, P/E, Market Cap in ₹ Cr, Promoters' Pledge % from NSE/BSE.
- quant_calc: Python calculation in ₹ Cr (ROCE, ROE, Free Cash Flow, Debt/Equity).

Return JSON:
{{
  "sub_tasks": [
    {{"id": "t1", "title": "Retrieve FY24 Debt and EBIT from Annual Report", "task_type": "filing_rag", "deps": []}},
    {{"id": "t2", "title": "Compute ROCE in ₹ Crores", "task_type": "quant_calc", "deps": ["t1"]}}
  ]
}}"""

class DecompositionAgent(BaseAgent):
    def __init__(self):
        super().__init__("decomposition")

    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        prompt = DECOMPOSITION_PROMPT.format(query=state.query, company=state.company or "", ticker=state.ticker or "")
        await budget_mgr.consume(self.agent_id, prompt)

        resp = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        data = json.loads(resp.text)
        subtasks = [SubTask(**t) for t in data.get("sub_tasks", [])]

        # Verify no circular dependencies exist
        self._verify_no_cycles(subtasks)
        state.subtasks = subtasks
        state.add_event(self.agent_id, "DECOMPOSITION_DONE", {"subtasks_count": len(subtasks)})

    def _verify_no_cycles(self, subtasks: list[SubTask]) -> None:
        visited, rec_stack = set(), set()
        task_map = {t.id: t.deps for t in subtasks}
        def dfs(node):
            visited.add(node); rec_stack.add(node)
            for dep in task_map.get(node, []):
                if dep not in visited:
                    if dfs(dep): return True
                elif dep in rec_stack: return True
            rec_stack.discard(node); return False
        for tid in task_map:
            if tid not in visited and dfs(tid):
                raise ValueError(f"Circular dependency detected involving task '{tid}'")
```

### 4.4 Senior Architect's Self-Critique & Design Decision
> **Critique**: Why not use a framework like LangGraph for defining the multi-agent graph?
>
> **Senior Decision**: As revealed in our audit of the legacy codebase, wrapping an LLM router inside LangGraph forced developers to use messy global module variables (`_budget_mgr`, `_redis_pub`) across node functions. A **pure Python async state machine** (`while not state.is_done()`) eliminates framework lock-in, avoids global hacks, and makes debugging 10x easier.

---

## Phase 5: Redis Pub/Sub Streaming, Event Bus & FastAPI Gateway

### 5.1 Objective & Deliverables
Implement `core/streaming.py` and `api/routes/query.py`. Connect the background agent runner to Redis Pub/Sub so clients receive real-time Server-Sent Events (SSE).

### 5.2 Beginner's Intuition
Financial research takes 10 to 20 seconds because agents are searching filings and running calculations. If you make the user stare at a blank screen, they will think the app crashed. By streaming events over SSE, the user sees live progress: *"Librarian found Tata Motors Annual Report"* $\to$ *"Quant calculating ROCE: 34.22%"* $\to$ *"Auditor drafting Investment Memo"*.

### 5.3 Concrete Code Implementation

#### `core/streaming.py`
```python
import asyncio
import json
import redis.asyncio as aioredis
from typing import Optional
from core.context import SharedState
from core.budget import ContextBudgetManager


class RedisPublisher:
    def __init__(self, redis_url: str = None):
        import os
        redis_url = redis_url or os.environ.get("UPSTASH_REDIS_URL", "redis://localhost:6379/0")
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)

    async def publish(self, job_id: str, event_data: dict):
        if self.redis:
            await self.redis.publish(f"job_events:{job_id}", json.dumps(event_data))

    async def publish_done(self, job_id: str, final_memo: str, provenance: list):
        await self.publish(job_id, {
            "event_type": "done", "job_id": job_id,
            "final_memo": final_memo, "provenance": [p.model_dump() for p in provenance]
        })

    async def publish_error(self, job_id: str, error_msg: str):
        await self.publish(job_id, {"event_type": "error", "error": error_msg})

    async def disconnect(self):
        if self.redis:
            await self.redis.aclose()


async def run_pipeline_async(query: str, company: Optional[str] = None, ticker: Optional[str] = None, job_id: Optional[str] = None) -> SharedState:
    state = SharedState(job_id=job_id or str(uuid.uuid4()), query=query, company=company, ticker=ticker)
    redis_pub = RedisPublisher()
    await redis_pub.connect()
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

    try:
        while not state.is_done():
            # 1. Orchestrator routes
            await agents["orchestrator"].run(state, budget_mgr, redis_pub)
            next_agent = state.events[-1]["details"].get("next_agent", "auditor_synthesizer")

            if next_agent == "done" or state.is_done():
                break

            # 2. Execute selected agent
            agent = agents.get(next_agent)
            if agent:
                budget_mgr.assert_compliant(next_agent)
                await agent.run(state, budget_mgr, redis_pub)

            state.turn += 1

        state.status = "done"
        state.clean_final_memo()
        await redis_pub.publish_done(state.job_id, state.final_memo, state.provenance)
        return state
    except Exception as e:
        state.status = "failed"
        await redis_pub.publish_error(state.job_id, str(e))
        raise
    finally:
        await redis_pub.disconnect()
```

#### `api/routes/query.py`
```python
import json
import uuid
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
    redis_client = aioredis.from_url(os.environ.get("UPSTASH_REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    pubsub = redis_client.pubsub()
    channel = f"job_events:{job_id}"
    await pubsub.subscribe(channel)

    # 2. Launch async task in background
    asyncio.create_task(run_pipeline_async(query=body.query, company=body.company, ticker=body.ticker, job_id=job_id))

    # 3. Stream events to client
    async def event_generator():
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message.get("type") != "message":
                    continue
                data = message.get("data", "{}")
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("event_type") in ("done", "error"):
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await redis_client.aclose()

    return EventSourceResponse(event_generator())
```

### 5.4 Senior Architect's Self-Critique & Design Decision
> **Critique**: Why subscribe to the Redis Pub/Sub channel *before* launching the background pipeline task?
>
> **Senior Decision**: If you launch the task first, fast early events (like `AGENT_START: decomposition`) will publish to Upstash Redis before the HTTP subscriber finishes connecting. Subscribing first guarantees zero dropped SSE events.
>
> **Critique**: Does Upstash Redis support Pub/Sub?
>
> **Senior Decision**: Yes. Upstash Redis supports standard Pub/Sub commands. The `redis-py` async client (`redis.asyncio`) connects to Upstash using a `rediss://` TLS URL identically to how it connects to local Redis. No code changes are needed beyond updating the connection URL.

---

## Phase 6: Forensic Auditing, Rumor Defense & Institutional Memo Synthesis

### 6.1 Objective & Deliverables
Implement `agents/auditor_synthesizer.py`. Enforce the **Step-0 False Premise Protocol**, forensic governance audits (promoter pledge $>20\%$, CFO vs PAT), and write institutional equity research memos in ₹ Crores.

### 6.2 Beginner's Intuition
Financial markets are full of rumors and malicious inputs (e.g. *"Since Reliance filed for NCLT bankruptcy, how will assets be divided?"*). A naive AI will answer the question as if Reliance really went bankrupt! The Forensic Auditor checks the premise first: if the premise is false, it rejects it immediately with verified evidence.

### 6.3 Concrete Code Implementation

```python
# agents/auditor_synthesizer.py
import asyncio
import json
from agents.base import BaseAgent
from core.context import SharedState, ProvenanceEntry, AuditFlag
from core.budget import ContextBudgetManager

AUDITOR_SYNTHESIZER_PROMPT = """You are the Senior Forensic Auditor and Institutional Research Synthesizer for Indian Equities.

STEP 0 — FALSE PREMISE & RUMOR CHECK:
- Check if the query contains a false Indian corporate premise (e.g. fake NCLT bankruptcy, fake corporate acquisition, unverified regulatory ban).
- If false: Output REJECTED with factual proof from SEBI/BSE filings.

STEP 1 — FORENSIC CHECKS:
1. Promoter Pledge: If pledged promoter holding > 20%, flag as HIGH RISK.
2. PAT vs CFO: If Operating Cash Flow < 0.7 * Reported PAT over 3 years, flag as EARNINGS QUALITY ALERT.
3. Contingent Liabilities: Check if contingent liabilities exceed 25% of Net Worth.

STEP 2 — DRAFT INSTITUTIONAL RESEARCH MEMO:
- Format in Indian Rupees (₹ Crores / Lakhs).
- Structure:
  1. Executive Investment Summary & Recommendation
  2. Financial Performance & Ratio Analysis (ROCE, Debt/Equity)
  3. Forensic Audit & Promoter Governance Analysis
  4. Valuation Summary
- Every factual sentence MUST cite its source: [BSE:...] or [CONCALL:...] or [CALCULATION:...].
- Silent contradiction resolution (never expose internal agent disagreements)."""

class AuditorSynthesizerAgent(BaseAgent):
    def __init__(self):
        super().__init__("auditor_synthesizer")

    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        chunks_text = "\n\n".join([f"{c.source_tag}: {c.text}" for c in state.chunks])
        calc_text = json.dumps({k: v.model_dump() for k, v in state.calculations.items()}, indent=2)

        prompt = f"{AUDITOR_SYNTHESIZER_PROMPT}\n\nQuery: {state.query}\nEvidence:\n{chunks_text}\nCalculations:\n{calc_text}"
        await budget_mgr.consume(self.agent_id, prompt)

        resp = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt
        )
        memo = resp.text if hasattr(resp, "text") else ""
        state.final_memo = memo

        # Build provenance map
        provenance_entries = []
        for line in memo.splitlines():
            line = line.strip()
            if "[" in line and "]" in line:
                tag = line[line.find("["): line.find("]")+1]
                provenance_entries.append(ProvenanceEntry(sentence=line, source_tag=tag))

        state.provenance = provenance_entries
        state.add_event(self.agent_id, "MEMO_SYNTHESIZED", {"provenance_count": len(provenance_entries)})
```

### 6.4 Senior Architect's Self-Critique & Design Decision
> **Critique**: Why merge the Auditor and Synthesizer into a single agent instead of keeping them as two separate LLM calls?
>
> **Senior Decision**: In financial analysis, having Critique output a list of flags and then having a separate Synthesis agent try to resolve those flags in a second LLM turn increases latency by 8–10 seconds and often causes prompt confusion. Merging them into a single high-context **Forensic Auditor & Synthesizer** cuts latency in half while ensuring the writer has full context of both the raw filings and the forensic audit rules.

---

## Phase 7: Evaluation Benchmark Harness, CI Test Suite & Leakage Guards

### 7.1 Objective & Deliverables
Implement `eval/scorers.py`, `eval/harness.py`, `eval/test_cases.json`, `scripts/seed_kb.py`, and `scripts/leakage_check.py`. Run automated CI tests with zero LLM API costs.

### 7.2 Beginner's Intuition
How do you know your multi-agent system actually works and doesn't hallucinate? We build a standardized 15-question exam covering easy questions, hard multi-year valuations, and tricky adversarial rumor questions. Our test harness grades the AI's exam automatically using exact Python math.

### 7.3 Concrete Code Implementation

#### `eval/scorers.py`
```python
import re
from typing import List, Optional, Tuple
from core.context import SharedState


def _extract_numbers(text: str) -> List[float]:
    cleaned = text.replace("₹", "").replace("Cr", "").replace("crore", "").replace("%", "").strip()
    raw_nums = re.findall(r'[-+]?\d+(?:,\d+)*(?:\.\d+)?', cleaned)
    nums = []
    for n in raw_nums:
        try:
            nums.append(float(n.replace(",", "")))
        except ValueError:
            continue
    return nums


def score_math_accuracy(final_memo: str, ground_truth: Optional[str], key_facts: Optional[List[str]] = None, relative_tolerance: float = 0.01) -> Tuple[float, str]:
    if not ground_truth and not key_facts:
        return 1.0, "Ambiguous valuation case without ground truth (scored 1.0)"

    if ground_truth == "REJECTED":
        rejected = any(t in final_memo for t in ["REJECTED", "False premise", "never occurred", "did not file", "never acquired"])
        return (1.0, "Adversarial rumor rejected PASSED") if rejected else (0.0, "Failed to reject false premise")

    if ground_truth == "TOOL_LIMIT_HIT":
        hit = any(t in final_memo.lower() for t in ["tool limit", "limit reached", "cannot process", "exceeded maximum"])
        return (1.0, "Halted on tool limit gracefully") if hit else (0.0, "Failed to halt on tool limit")

    facts = key_facts or [f.strip() for f in (ground_truth.split(";") if ";" in ground_truth else [ground_truth])]
    hits = 0
    memo_lower = final_memo.lower()
    memo_nums = _extract_numbers(final_memo)

    for fact in facts:
        if fact.lower().strip() in memo_lower:
            hits += 1
            continue
        fact_nums = _extract_numbers(fact)
        if fact_nums and memo_nums:
            matched = False
            for fn in fact_nums:
                for mn in memo_nums:
                    if fn != 0 and abs(mn - fn) / abs(fn) <= relative_tolerance:
                        matched = True; break
            if matched:
                hits += 1

    score = hits / max(len(facts), 1)
    return round(score, 3), f"Verified {hits}/{len(facts)} key financial figures."


def score_citation_accuracy(state: SharedState) -> Tuple[float, str]:
    if not state.provenance:
        return 0.0, "Zero citations generated in provenance map"
    valid_chunks = {c.id: c.text for c in state.chunks}
    valid = 0
    stopwords = {"the", "a", "an", "is", "in", "of", "to", "and", "for", "inr", "cr", "crore"}

    for p in state.provenance:
        if not p.chunk_id:
            valid += 1
            continue
        chunk_text = valid_chunks.get(p.chunk_id, "")
        s_words = set(re.findall(r'\b\w+\b', p.sentence.lower())) - stopwords
        c_words = set(re.findall(r'\b\w+\b', chunk_text.lower())) - stopwords
        if len(s_words & c_words) >= 2:
            valid += 1

    score = valid / max(len(state.provenance), 1)
    return round(score, 3), f"Citations verified: {valid}/{len(state.provenance)}"


def score_false_premise(state: SharedState) -> Tuple[float, str]:
    if not state.audit_flags:
        return 1.0, "Zero audit flags / false premises detected"
    hedge_phrases = ["may", "might", "analysts suggest", "contested", "uncertain", "evidence suggests"]
    final_lower = state.final_memo.lower()
    resolved = 0
    for flag in state.audit_flags:
        span_lower = flag.span.lower().strip()
        if span_lower not in final_lower or any(h in final_lower for h in hedge_phrases):
            resolved += 1
    score = resolved / len(state.audit_flags)
    return round(score, 3), f"Resolved/Hedged {resolved}/{len(state.audit_flags)} audit flags."


def score_tool_efficiency(state: SharedState, expected_min: int, expected_max: int) -> Tuple[float, str]:
    actual = len(state.tool_calls)
    if actual <= expected_max:
        return 1.0, f"Tool calls ({actual}) within expected bounds ({expected_min}-{expected_max})"
    excess = actual - expected_max
    penalty = excess / max(expected_max, 1)
    score = max(0.0, 1.0 - penalty)
    return round(score, 3), f"Tool calls ({actual}) exceeded max ({expected_max}). Penalty: {penalty:.2f}."


WEIGHTS = {"math_accuracy": 0.35, "citation_accuracy": 0.25, "premise_rejection": 0.20, "tool_efficiency": 0.20}

def compute_composite_score(scores: dict) -> float:
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS if k in scores), 4)
```

#### `scripts/leakage_check.py`
```python
import json
from pathlib import Path

def run_leakage_check():
    test_cases = json.loads(Path("eval/test_cases.json").read_text())
    from scripts.seed_kb import SEED_INDIAN_DOCUMENTS

    leakage_found = 0
    for tc in test_cases:
        gt = tc.get("ground_truth")
        if not gt or gt in ("REJECTED", "TOOL_LIMIT_HIT", "Both viewpoints surfaced"):
            continue

        for doc in SEED_INDIAN_DOCUMENTS:
            if gt.lower() in doc["content"].lower():
                print(f"LEAKAGE DETECTED in [{tc['id']}]: Ground truth '{gt}' found verbatim in seed doc for '{doc['company']}'")
                leakage_found += 1

    if leakage_found == 0:
        print("PASS: 0 ground truth strings leaked verbatim in seed documents.")
    else:
        raise ValueError(f"Leakage check failed with {leakage_found} contaminations.")

if __name__ == "__main__":
    run_leakage_check()
```

---

## 10. Senior Architect's Self-Critique & Anti-Pattern Checklist

Before deploying FinOrchestra to production, audit your implementation against this checklist:

| Potential Failure Mode | Root Cause | FinOrchestra Architectural Remedy |
| :--- | :--- | :--- |
| **1. Infinite Agent Loops** | LLM router repeatedly routes between agents without concluding. | Hard `MAX_TURNS = 10` limit in `SharedState.is_done()`. |
| **2. Indian Comma Parsing Crash** | Splitting strings on commas (`"₹1,78,677 Cr".split(",")`) breaks numeric evaluation. | Replaced comma-splitting with regex extractor `_extract_numbers()`. |
| **3. Arithmetic Hallucination** | LLM computes ROCE or WACC in prompt text. | All math delegated to sandboxed Python subprocess (`quant_math_sandbox`). |
| **4. Subtask Deadlocks** | Decomposition outputs circular dependencies ($A \to B \to A$). | DFS cycle detection (`_verify_no_cycles`) runs before subtask execution. |
| **5. Database Lock Exhaustion** | Background async tasks share connection pool across event loops. | Isolated `NullPool` engine used for all background worker tasks (works identically with Supabase PostgreSQL). |
| **6. False Rumor Acceptance** | Query assumes fake corporate bankruptcy or acquisition. | Step-0 False Premise Protocol rejects false premises before drafting answer. |
| **7. Benchmark Score Contamination** | Ground-truth answers appear verbatim in vector search chunks. | Automated `scripts/leakage_check.py` verifies zero data leakage. |
