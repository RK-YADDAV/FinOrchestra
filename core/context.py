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
    company: str                   # e.g., "Reliance Industries", "TCS", "HDFC Bank"
    ticker: str                    # e.g., "RELIANCE", "TCS", "HDFCBANK"
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

    # 1. Planning & Subtasks DAG
    subtasks: List[SubTask] = Field(default_factory=list)

    # 2. Retrieved Indian Financial Evidence
    chunks: List[RetrievedChunk] = Field(default_factory=list)

    # 3. Deterministic Calculations (in ₹ Crores) & Tool Calls
    calculations: Dict[str, CalculationResult] = Field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)

    # 4. Forensic Auditing & Flags
    audit_flags: List[AuditFlag] = Field(default_factory=list)

    # 5. Final Synthesis & Provenance Map
    final_memo: str = ""
    provenance: List[ProvenanceEntry] = Field(default_factory=list)

    # 6. Token Budget & Event Log
    used_tokens: int = 0
    max_tokens: int = 24000
    events: List[Dict[str, Any]] = Field(default_factory=list)

    def is_done(self) -> bool:
        return self.status in ("done", "failed") or self.turn >= 10

    def get_chunk_by_id(self, chunk_id: str) -> Optional[RetrievedChunk]:
        return next((c for c in self.chunks if c.id == chunk_id), None)

    def clean_final_memo(self) -> None:
        """Strip raw [BSE:...] tags from user prose while preserving provenance entries."""
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
