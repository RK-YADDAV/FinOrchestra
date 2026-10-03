import json
import asyncio
import re
from core.context import SharedState, RetrievedChunk
from core.budget import ContextBudgetManager
from core.tools import execute_tool_with_retry, tool_filings_rag
from agents.base import BaseAgent
from db.session import get_isolated_engine

RETRIEVAL_HOP1_PROMPT = """You are an Indian Financial Filing Retrieval Agent (Hop 1).
Analyze the retrieved BSE/NSE annual report chunks and concall transcripts.

Query: {query}
Retrieved Chunks:
{chunks}

Tasks:
1. Extract key reported figures in ₹ Crores (Revenue, EBITDA, PAT, Net Debt).
2. Identify missing footnotes (e.g. Note 32 Related Party Transactions, Contingent Liabilities).
3. Output on a new line:
SECOND_HOP_QUERY: <targeted search query for missing disclosures or notes>
If no missing notes, output: SECOND_HOP_QUERY: NONE"""

class IndianFilingRetrievalAgent(BaseAgent):
    def __init__(self):
        super().__init__("retrieval")

    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        db_engine = get_isolated_engine(readonly=True)
        
        try:
            # Execute Hop 1 Retrieval
            res = await execute_tool_with_retry(
                tool_fn=tool_filings_rag,
                tool_name="tool_filings_rag",
                agent_id=self.agent_id,
                state=state,
                tool_kwargs={
                    "query": state.query,
                    "ticker": state.ticker,
                    "db_engine": db_engine,
                    "embed_client": self.client,
                    "limit": 5
                },
                max_retries=2
            )
            
            if res.success and res.data:
                for chunk_data in res.data.get("chunks", []):
                    chunk = RetrievedChunk(
                        id=chunk_data["id"],
                        company=chunk_data["company"],
                        ticker=chunk_data["ticker"],
                        document_type=chunk_data["doc_type"],
                        text=chunk_data["text"],
                        source_tag=f"[BSE:{chunk_data['ticker']}:{chunk_data['doc_type']}]",
                        relevance_score=chunk_data["relevance"]
                    )
                    state.chunks.append(chunk)

            if not state.chunks:
                state.add_event(self.agent_id, "RETRIEVAL_DONE", {"chunks_retrieved": 0})
                return

            # Execute Hop 2 Logic
            chunks_text = "\n\n".join([f"[{c.source_tag}] {c.text}" for c in state.chunks])
            prompt = RETRIEVAL_HOP1_PROMPT.format(query=state.query, chunks=chunks_text)
            
            await budget_mgr.consume(self.agent_id, prompt)
            resp = await self._call_llm(prompt)
            
            second_hop_query = None
            for line in resp.text.splitlines():
                if line.strip().startswith("SECOND_HOP_QUERY:"):
                    q = line.split("SECOND_HOP_QUERY:")[1].strip()
                    if q and q.upper() != "NONE":
                        second_hop_query = q
                    break

            if second_hop_query:
                state.add_event(self.agent_id, "RETRIEVAL_HOP2_START", {"query": second_hop_query})
                res2 = await execute_tool_with_retry(
                    tool_fn=tool_filings_rag,
                    tool_name="tool_filings_rag",
                    agent_id=self.agent_id,
                    state=state,
                    tool_kwargs={
                        "query": second_hop_query,
                        "ticker": state.ticker,
                        "db_engine": db_engine,
                        "embed_client": self.client,
                        "limit": 3
                    },
                    max_retries=2
                )
                if res2.success and res2.data:
                    for chunk_data in res2.data.get("chunks", []):
                        # Avoid duplicates
                        if not any(c.id == chunk_data["id"] for c in state.chunks):
                            chunk = RetrievedChunk(
                                id=chunk_data["id"],
                                company=chunk_data["company"],
                                ticker=chunk_data["ticker"],
                                document_type=chunk_data["doc_type"],
                                text=chunk_data["text"],
                                source_tag=f"[BSE:{chunk_data['ticker']}:{chunk_data['doc_type']}]",
                                relevance_score=chunk_data["relevance"]
                            )
                            state.chunks.append(chunk)
            
            state.add_event(self.agent_id, "RETRIEVAL_DONE", {"chunks_retrieved": len(state.chunks)})
            
        finally:
            await db_engine.dispose()
