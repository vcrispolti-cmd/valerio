"""Run-state data model: claims, evidence, sources, issues.

The claim register is the central database. Drafts are views over approved
claims; they never become the record.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def grade_value(grade: str | None) -> int:
    """'S4' -> 4, 'E2' -> 2, None/'' -> -1 (ungraded)."""
    if not grade or len(grade) < 2 or not grade[1:].isdigit():
        return -1
    return int(grade[1:])


@dataclass
class Evidence:
    source_id: str
    excerpt: str                      # verbatim passage from the source
    locator: str = ""                 # page / table / paragraph
    relation: str = "supports"        # supports | partial | contradicts
    proposed_by: str = ""
    quote_check: str = "NOT_CHECKED"  # FOUND | FOUND_APPROX | NOT_FOUND | SOURCE_UNAVAILABLE | NOT_CHECKED
    match_score: float = 0.0


@dataclass
class NumberFact:
    value: float
    unit: str = ""
    series: str = ""
    country: str = ""
    period: str = ""
    connector: str = ""               # data connector id (e.g. local_csv, worldbank)
    formula: str = ""                 # optional derivation, e.g. "a - b"
    inputs: dict = field(default_factory=dict)
    data_check: str = "UNCHECKED"     # MATCH | MISMATCH | NOT_FOUND | UNCHECKED | DERIVED_OK | DERIVED_MISMATCH
    observed: float | None = None


@dataclass
class Claim:
    claim_id: str
    text: str
    claim_type: str
    importance: str = "MATERIAL"
    author: str = ""                  # agent that first proposed the claim
    status: str = "PROPOSED"
    approved_wording: str = ""
    current: bool = True              # presented as describing current conditions
    evidence: list = field(default_factory=list)       # list[Evidence]
    numbers: list = field(default_factory=list)        # list[NumberFact]
    grades: dict = field(default_factory=dict)         # grader agent -> {S,E,C}
    audit: dict = field(default_factory=dict)          # auditor agent -> {status, excerpt, source_id, ...}
    alternatives: list = field(default_factory=list)
    contradictions: list = field(default_factory=list) # [{source_id, note, resolved: bool}]
    qualifications: list = field(default_factory=list)
    depends_on: list = field(default_factory=list)
    recommendation_chain: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    history: list = field(default_factory=list)

    # Conservative consensus: the MINIMUM grade any independent grader gave.
    def consensus(self, dim: str) -> str | None:
        vals = [grade_value(g.get(dim)) for g in self.grades.values() if grade_value(g.get(dim)) >= 0]
        if not vals:
            return None
        return f"{dim}{min(vals)}"

    def spread(self, dim: str) -> int:
        vals = [grade_value(g.get(dim)) for g in self.grades.values() if grade_value(g.get(dim)) >= 0]
        return max(vals) - min(vals) if len(vals) > 1 else 0

    def wording(self) -> str:
        return self.approved_wording or self.text

    def log(self, event: str) -> None:
        self.history.append(f"{now()} {event}")

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        known = {f.name for f in fields(cls)}
        c = cls(**{k: v for k, v in d.items() if k in known})
        c.evidence = [e if isinstance(e, Evidence) else Evidence(**_known(Evidence, e)) for e in c.evidence]
        c.numbers = [n if isinstance(n, NumberFact) else NumberFact(**_known(NumberFact, n)) for n in c.numbers]
        return c


@dataclass
class Source:
    source_id: str
    title: str
    institution: str = ""
    publication_date: str = ""        # YYYY-MM-DD
    data_vintage: str = ""            # e.g. "WEO April 2026"
    url: str = ""
    local_path: str = ""
    authority_grade: str = ""
    status: str = "UNCHECKED"         # CONFIRMED | UNAVAILABLE | UNREADABLE | UNCHECKED
    sha256: str = ""
    retrieved_at: str = ""
    proposed_by: str = ""
    limitations: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(**_known(cls, d))


@dataclass
class Issue:
    issue_id: str
    raised_by: str                    # agent or "system"
    stage: str
    category: str                     # factual | source_gap | numeric | causal | alternative | analytical | grading | coverage | framing | synthesis | drafting | editorial | security
    severity: str                     # RED | YELLOW | GREEN
    description: str
    claim_ids: list = field(default_factory=list)
    proposed_resolution: str = ""
    disposition: dict = field(default_factory=dict)   # {decision, by, rationale, at}
    rebuttal: dict = field(default_factory=dict)      # {verdict: UPHELD|WITHDRAWN, by, rationale}
    ruling: dict = field(default_factory=dict)        # {verdict: FOR_CRITIC|FOR_SYNTHESIZER|ESCALATE, by, rationale}
    status: str = "OPEN"              # OPEN | RESOLVED | HUMAN_REQUIRED
    key: str = ""                     # stable key for system-raised issues (idempotent re-checks)
    resolution_note: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Issue":
        return cls(**_known(cls, d))


@dataclass
class RunState:
    run_id: str
    research_question: str
    document_type: str
    confidentiality: str
    mode: str
    requested_level: int
    level: int = 0
    level_basis: list = field(default_factory=list)
    country: str = ""
    as_of: str = ""
    context: str = ""
    assignments: dict = field(default_factory=dict)
    framing: dict = field(default_factory=dict)
    neutral_subquestions: list = field(default_factory=list)
    track_outputs: dict = field(default_factory=dict)
    claims: dict = field(default_factory=dict)        # claim_id -> Claim
    sources: dict = field(default_factory=dict)       # source_id -> Source
    issues: list = field(default_factory=list)        # list[Issue]
    coverage: dict = field(default_factory=dict)
    synthesis: dict = field(default_factory=dict)
    drafts: dict = field(default_factory=dict)
    final_audit: list = field(default_factory=list)
    gates: dict = field(default_factory=dict)
    iteration: int = 1
    stages_done: list = field(default_factory=list)
    reliability: dict = field(default_factory=dict)   # agent -> counters
    notes: list = field(default_factory=list)

    def next_claim_id(self) -> str:
        n = 1 + max([int(c[1:]) for c in self.claims if c[1:].isdigit()] or [0])
        return f"C{n:03d}"

    def add_issue(self, **kw) -> Issue:
        issue = Issue(issue_id=f"I{len(self.issues) + 1:03d}", **kw)
        self.issues.append(issue)
        return issue

    def bump(self, agent: str, counter: str, by: int = 1) -> None:
        self.reliability.setdefault(agent, {}).setdefault(counter, 0)
        self.reliability[agent][counter] += by

    def to_json(self) -> dict:
        d = asdict(self)
        return d

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")


def _known(cls, d: dict) -> dict:
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in names}
