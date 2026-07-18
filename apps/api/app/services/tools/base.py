from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["critical", "high", "medium", "low", "info"]

# Deducted from a starting score of 100, per finding, by severity. Shared
# across every tool so scores are comparable to each other in the merged
# report's Critical/High/Medium/Low fix list.
SEVERITY_WEIGHT: dict[Severity, int] = {
    "critical": 25,
    "high": 15,
    "medium": 8,
    "low": 3,
    "info": 0,
}


@dataclass
class Finding:
    severity: Severity
    code: str
    message: str


@dataclass
class ToolResult:
    tool: str
    status: Literal["ok", "error"]
    score: int | None
    findings: list[Finding] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "status": self.status,
            "score": self.score,
            "findings": [f.__dict__ for f in self.findings],
            "raw": self.raw,
        }


def score_from_findings(findings: list[Finding]) -> int:
    score = 100 - sum(SEVERITY_WEIGHT[f.severity] for f in findings)
    return max(0, min(100, score))


ToolFn = Callable[[str], Awaitable[ToolResult]]
TOOL_REGISTRY: dict[str, ToolFn] = {}


def register_tool(name: str) -> Callable[[ToolFn], ToolFn]:
    def decorator(fn: ToolFn) -> ToolFn:
        TOOL_REGISTRY[name] = fn
        return fn

    return decorator
