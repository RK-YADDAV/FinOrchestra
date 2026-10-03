# FinOrchestra India 🇮🇳

**FinOrchestra** is an autonomous, multi-agent financial research orchestrator specifically designed for Indian Equities (NSE/BSE). It unifies semantic document retrieval (RAG) on dense SEBI disclosures with deterministic Python-based quantitative calculations.

Powered by a swarm of specialized LLM subagents, FinOrchestra automatically decomposes complex financial queries, retrieves exact metrics from Annual Reports and Earnings Transcripts, runs deterministic mathematical sandboxes, and synthesizes institutional-grade investment memos.

---

## 🏗️ Core Architecture

FinOrchestra relies on a highly specialized Multi-Agent Swarm architecture:

1. **Orchestrator Agent**: The central router. Analyzes the current "Blackboard" state and dynamically delegates tasks.
2. **Decomposition Agent**: Breaks down ambiguous user queries into strict, typed subtasks (e.g., `filing_rag`, `quant_calc`).
3. **Retrieval Agent (RAG)**: Queries local vector embeddings of Indian corporate filings (Annual Reports, SEBI LODR Regulation 33, Transcripts) to isolate factual context.
4. **QuantRunner Agent**: Autonomously writes and executes Python code in a secure sandbox to calculate exact financial metrics (ROCE, P/E, Cash Flow Margins) from structured SQL databases.
5. **Auditor & Synthesizer Agent**: The final step. Reviews the raw data and calculations, aggressively rejects false premises/rumors (anti-hallucination), and formats an institutional memo with strict citations.

---

## ⚙️ Tech Stack

* **LLM Engine:** Google Gemini (`gemini-3.6-flash` via the GenAI SDK)
* **Local Embeddings:** `SentenceTransformer` (`all-MiniLM-L6-v2` - 384 dimensions)
* **Database & Vector Store:** Supabase PostgreSQL with `pgvector`
* **Event Streaming:** Upstash Redis (or local `asyncio.Queue` mocks for testing)
* **Data Ingestion:** `langchain-text-splitters` for granular semantic chunking (1000 chunk size / 200 overlap).

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
Ensure you have Python 3.12+ installed and an active [Google Gemini API Key](https://aistudio.google.com/). You will also need a [Supabase](https://supabase.com) project for PostgreSQL vector storage.

### 2. Installation
Clone the repository and install the dependencies in a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```env
GOOGLE_API_KEY=your_gemini_key
DATABASE_URL=postgresql+asyncpg://postgres.yourproject:password@your-supabase-url.com:5432/postgres
# (Optional) UPSTASH_REDIS_URL for distributed event streaming
```

### 4. Database Setup & Seeding
Initialize your database and seed it with the mock data and locally embedded PDF chunks:
```bash
# This will truncate existing tables and seed 1400+ vectors from the data/ PDFs
PYTHONPATH=. python scripts/ingest_pdfs.py
PYTHONPATH=. python scripts/seed_kb.py
```

---

## 🧪 Evaluation & Benchmarking

FinOrchestra includes a comprehensive, automated evaluation harness (`eval/harness.py`). The harness runs the agent swarm through a rigorous suite of queries designed to test Math Accuracy, Citation Gounding, and Adversarial Premise Rejection.

To run the evaluation suite:
```bash
make eval
```


## 📚 Documentation

For deep dives into the system design, check the `guide/` directory:

- [01. Architecture & Orchestration](guide/01_architecture_and_orchestration.md)
- [02. Financial Tools & Failure Contracts](guide/02_financial_tools_and_failure_contracts.md)
- [03. Evaluation Testing & Benchmarks](guide/03_evaluation_testing_and_benchmarks.md)
- [04. Evaluation Results & Infrastructure Upgrades](guide/04_evaluation_results_and_upgrades.md) *(Start Here for latest architecture changes)*
- [Agents Overview](guide/agents.md)

