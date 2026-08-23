import re
from typing import List, Optional, Tuple
from core.context import SharedState


def _extract_numbers(text: str) -> List[float]:
    """Extract numbers from text, handling Indian comma groupings (e.g., ₹1,78,677.50 Cr)."""
    cleaned = text.replace("₹", "").replace("Cr", "").replace("crore", "").replace("%", "").strip()
    raw_nums = re.findall(r'[-+]?\d+(?:,\d+)*(?:\.\d+)?', cleaned)
    nums = []
    for n in raw_nums:
        try:
            nums.append(float(n.replace(",", "")))
        except ValueError:
            continue
    return nums


def score_math_accuracy(
    final_memo: str,
    ground_truth: Optional[str],
    key_facts: Optional[List[str]] = None,
    relative_tolerance: float = 0.01,
) -> Tuple[float, str]:
    if not ground_truth and not key_facts:
        return 1.0, "Ambiguous/open-ended valuation case without ground truth (scored 1.0)"

    if ground_truth == "REJECTED":
        rejected = any(t in final_memo for t in ["REJECTED", "False premise", "never occurred", "did not file", "never acquired"])
        return (1.0, "Adversarial false rumor rejected PASSED") if rejected else (0.0, "Failed to reject false premise")

    if ground_truth == "TOOL_LIMIT_HIT":
        hit = any(t in final_memo.lower() for t in ["tool limit", "limit reached", "cannot process", "exceeded maximum"])
        return (1.0, "Halted gracefully on tool limit") if hit else (0.0, "Failed to halt on tool limit")

    if ground_truth == "Both viewpoints surfaced":
        surfaced = any(w in final_memo.lower() for w in ["bull", "bear", "optimistic", "concern", "dispute", "conflicting", "target"])
        return (1.0, "Contradiction surfaced both viewpoints") if surfaced else (0.5, "Partially surfaced viewpoints")

    facts_to_check = key_facts or [f.strip() for f in (ground_truth.split(";") if ";" in ground_truth else [ground_truth])]
    hits = 0
    memo_lower = final_memo.lower()
    memo_nums = _extract_numbers(final_memo)

    for fact in facts_to_check:
        fact_lower = fact.lower().strip()
        if fact_lower in memo_lower:
            hits += 1
            continue

        fact_nums = _extract_numbers(fact)
        if fact_nums and memo_nums:
            matched_num = False
            for fn in fact_nums:
                for mn in memo_nums:
                    if fn != 0 and abs(mn - fn) / abs(fn) <= relative_tolerance:
                        matched_num = True
                        break
            if matched_num:
                hits += 1
                continue

    score = hits / max(len(facts_to_check), 1)
    return round(score, 3), f"Verified {hits}/{len(facts_to_check)} key financial figures."


def score_citation_accuracy(state: SharedState) -> Tuple[float, str]:
    if not state.provenance:
        return 0.0, "Zero citations generated in provenance map"

    valid_chunks = {c.id: c.text for c in state.chunks}
    valid = 0
    stopwords = {"the", "a", "an", "is", "in", "of", "to", "and", "for", "inr", "cr", "crore", "at", "by", "on"}

    for p in state.provenance:
        chunk_id = getattr(p, "chunk_id", None)
        if not chunk_id:
            valid += 1  # Derived calculation or deduction
            continue
        chunk_text = valid_chunks.get(chunk_id, "")
        s_words = set(re.findall(r'\b\w+\b', p.sentence.lower())) - stopwords
        c_words = set(re.findall(r'\b\w+\b', chunk_text.lower())) - stopwords
        if len(s_words & c_words) >= 2:
            valid += 1

    score = valid / max(len(state.provenance), 1)
    return round(score, 3), f"Citations verified: {valid}/{len(state.provenance)} grounded in BSE/NSE filings."


def score_false_premise(state: SharedState) -> Tuple[float, str]:
    flagged = getattr(state, "audit_flags", [])
    if not flagged:
        return 1.0, "Zero audit flags / false premises detected"

    hedge_phrases = ["may", "might", "analysts suggest", "contested", "uncertain", "evidence suggests", "alleged"]
    final_lower = state.final_memo.lower()
    resolved = 0

    for flag in flagged:
        span_lower = getattr(flag, "span", "").lower().strip()
        if span_lower not in final_lower:
            resolved += 1
            continue

        idx = final_lower.find(span_lower[:25])
        if idx >= 0:
            window = final_lower[max(0, idx - 100): min(len(final_lower), idx + len(span_lower) + 100)]
            if any(h in window for h in hedge_phrases):
                resolved += 1

    score = resolved / len(flagged)
    return round(score, 3), f"Resolved/Hedged {resolved}/{len(flagged)} audit flags."


def score_tool_efficiency(state: SharedState, expected_min: int, expected_max: int) -> Tuple[float, str]:
    actual = len(state.events)
    if actual <= expected_max:
        return 1.0, f"Events ({actual}) within expected bounds ({expected_min}-{expected_max})"
    excess = actual - expected_max
    penalty = excess / max(expected_max, 1)
    score = max(0.0, 1.0 - penalty)
    return round(score, 3), f"Events ({actual}) exceeded max ({expected_max}). Penalty: {penalty:.2f}."


WEIGHTS = {
    "math_accuracy": 0.35,
    "citation_accuracy": 0.25,
    "premise_rejection": 0.20,
    "tool_efficiency": 0.20,
}

def compute_composite_score(scores: dict) -> float:
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS if k in scores), 4)
