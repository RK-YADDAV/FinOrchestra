import json
import asyncio
from core.context import SharedState, ProvenanceEntry
from core.budget import ContextBudgetManager
from agents.base import BaseAgent

AUDITOR_SYNTHESIZER_PROMPT = """You are the Senior Forensic Auditor and Institutional Research Synthesizer for Indian Equities.

STEP 0 \u2014 FALSE PREMISE & RUMOR CHECK:
- Check if the query contains a false Indian corporate rumor (e.g. fake NCLT bankruptcy, fake corporate acquisition, unverified regulatory bans).
- If false: Immediately output REJECTED with factual proof from SEBI/BSE filings.

STEP 1 \u2014 FORENSIC AUDIT CHECKS:
1. Promoter Pledge: If pledged promoter holding > 20%, flag as HIGH RISK.
2. PAT vs CFO: If Operating Cash Flow < 0.7 * Reported PAT over 3 years, flag as EARNINGS QUALITY ALERT.
3. Contingent Liabilities: Check if contingent liabilities exceed 25% of Net Worth.

STEP 2 \u2014 DRAFT INSTITUTIONAL RESEARCH MEMO:
- Currency: Indian Rupees (\u20b9 Crores / Lakhs).
- Structure:
  1. Investment Summary & Recommendation
  2. Operational & Financial Performance (Revenue, ROCE, Debt/Equity)
  3. Forensic Audit & Promoter Governance Analysis
  4. Valuation & Target Price Multiple
- Sentence-by-sentence citations using [BSE:...] or [CONCALL:...] tags.
- Silent contradiction resolution (never mention internal agent disagreements).

Context:
Query: {query}
Evidence: {chunks}
Calculations: {calculations}

Output your final synthesized memo directly."""

class AuditorSynthesizerAgent(BaseAgent):
    def __init__(self):
        super().__init__("auditor_synthesizer")

    async def run(self, state: SharedState, budget_mgr: ContextBudgetManager, redis_pub=None) -> None:
        chunks_text = "\n\n".join([f"[{c.source_tag}] {c.text}" for c in state.chunks])
        calc_text = json.dumps({k: {"value": v.output_value, "stdout": v.stdout} for k, v in state.calculations.items()})
        
        prompt = AUDITOR_SYNTHESIZER_PROMPT.format(
            query=state.query,
            chunks=chunks_text,
            calculations=calc_text
        )
        
        await budget_mgr.consume(self.agent_id, prompt)
        resp = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        state.final_memo = resp.text
        
        # Simple extraction of provenance tags
        import re
        tags = set(re.findall(r'\[(?:BSE|CONCALL):[^\]]+\]', resp.text))
        for tag in tags:
            state.provenance.append(ProvenanceEntry(sentence="Synthesized reference", source_tag=tag))
            
        # Optional: clean the final memo of raw tags to make it read better for the user
        state.clean_final_memo()
        
        state.add_event(self.agent_id, "AUDIT_SYNTHESIS_DONE", {"memo_length": len(state.final_memo)})
        state.status = "done"
