import json
import asyncio
import re
from core.context import SharedState, ProvenanceEntry, AuditFlag
from core.budget import ContextBudgetManager
from agents.base import BaseAgent

AUDITOR_SYNTHESIZER_PROMPT = """You are the Senior Forensic Auditor and Institutional Research Synthesizer for Indian Equities.

STEP 0 — FALSE PREMISE & RUMOR CHECK:
- Check if the query contains a false Indian corporate rumor (e.g. fake NCLT bankruptcy, fake corporate acquisition, unverified regulatory bans).
- If false: Immediately output REJECTED with factual proof from SEBI/BSE filings in the final_memo.

STEP 1 — FORENSIC AUDIT CHECKS:
1. Promoter Pledge: If pledged promoter holding > 20%, flag as HIGH RISK.
2. PAT vs CFO: If Operating Cash Flow < 0.7 * Reported PAT over 3 years, flag as EARNINGS QUALITY ALERT.
3. Contingent Liabilities: Check if contingent liabilities exceed 25% of Net Worth.

STEP 2 — DRAFT INSTITUTIONAL RESEARCH MEMO:
- Currency: Indian Rupees (₹ Crores / Lakhs).
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

Output MUST be a JSON object with this exact schema:
{{
  "audit_flags": [
    {{
      "flag_type": "promoter_pledge_high | false_premise | pat_ocf_divergence | contradiction",
      "span": "Relevant sentence or data snippet",
      "reason": "Detailed explanation of the flag",
      "severity": "HIGH | MEDIUM | LOW",
      "status": "FLAGGED | RESOLVED | HEDGED | REJECTED"
    }}
  ],
  "final_memo": "Your complete Markdown institutional memo here."
}}"""

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
            model="gemini-3.6-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        
        try:
            data = json.loads(resp.text)
        except Exception:
            clean_text = resp.text.strip().strip('```json').strip('```').strip()
            data = json.loads(clean_text)
            
        memo_text = data.get("final_memo", "")
        flags_data = data.get("audit_flags", [])
        
        for f in flags_data:
            state.audit_flags.append(AuditFlag(**f))
            
        state.final_memo = memo_text
        
        # Extract provenance tags
        tags = set(re.findall(r'\[(?:BSE|CONCALL|CALCULATION):[^\]]+\]', memo_text))
        for tag in tags:
            state.provenance.append(ProvenanceEntry(sentence="Synthesized reference", source_tag=tag))
            
        # Clean the final memo of raw tags to make it read better for the user
        state.clean_final_memo()
        
        state.add_event(self.agent_id, "AUDIT_SYNTHESIS_DONE", {
            "memo_length": len(state.final_memo),
            "flags_detected": len(state.audit_flags)
        })
        state.status = "done"
