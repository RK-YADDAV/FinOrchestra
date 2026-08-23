import re
from pydantic import BaseModel

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous\s+|prior\s+)?instructions",
    r"(?i)system\s+prompt",
    r"(?i)database\s+(password|credentials|connection\s+string)",
    r"(?i)reveal\s+(your\s+)?secret",
    r"(?i)dan\s+mode",
    r"(?i)jailbreak",
    r"(?i)bypass\s+security",
]

class InjectionResult(BaseModel):
    is_injection: bool
    confidence: float
    detected_pattern: str = ""

def detect_injection(query: str) -> InjectionResult:
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, query)
        if match:
            return InjectionResult(is_injection=True, confidence=1.0, detected_pattern=match.group(0))
    return InjectionResult(is_injection=False, confidence=0.0)
