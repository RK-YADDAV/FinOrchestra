import json
import asyncio
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
1. Extract key reported figures in \u20b9 Crores (Revenue, EBITDA, PAT, Net Debt).
2. Identify missing footnotes (e.g. Note 32 Related Party Transactions, Contingent Liabilities).
3. Output on a new line:
SECOND_HOP_QUERY: <targeted search query for missing disclosures or notes>"""

class RetrievalAgent(BaseAgent):
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

            # NOTE: Hop 2 logic is stubbed out for simplicity, 
            # in a full implementation we would call the LLM with RETRIEVAL_HOP1_PROMPT
            # parse out the SECOND_HOP_QUERY and call tool_filings_rag again.
            
            state.add_event(self.agent_id, "RETRIEVAL_DONE", {"chunks_retrieved": len(state.chunks)})
            
        finally:
            await db_engine.dispose()
