"""Output contracts: the JSON each role must return.

The contract text is appended to every prompt, and replies are checked against
the required keys before anything enters the run state.
"""
from __future__ import annotations

import json
import re

CONTRACTS: dict[str, dict] = {
    "framer": {
        "required": ["research_question", "premise_check", "neutral_subquestions", "definitions",
                     "hypotheses", "falsification_tests", "evidence_requirements"],
        "example": {
            "research_question": "restated neutrally",
            "premise_check": [{"premise": "the question assumes X", "established": "yes|no|unclear", "note": ""}],
            "neutral_subquestions": ["questions that do not presuppose an answer"],
            "definitions": [{"term": "", "definition": "", "source": ""}],
            "hypotheses": [{"id": "H1", "statement": "", "mechanism": "", "would_be_falsified_by": ""}],
            "falsification_tests": [""],
            "evidence_requirements": [{"need": "", "preferred_source": "", "series": ""}],
        },
    },
    "framing_challenger": {
        "required": ["loaded_premises", "missing_subquestions", "missing_hypotheses"],
        "example": {
            "loaded_premises": [{"premise": "", "why_loaded": "", "severity": "RED|YELLOW"}],
            "missing_subquestions": [""],
            "missing_hypotheses": [{"statement": "", "mechanism": ""}],
        },
    },
    "researcher": {
        "required": ["sources", "candidate_claims", "contradictions", "research_gaps"],
        "example": {
            "sources": [{"source_id": "S-tmp-1", "title": "", "institution": "", "publication_date": "YYYY-MM-DD",
                         "data_vintage": "", "url": "", "authority_grade": "S5", "limitations": []}],
            "candidate_claims": [{"text": "", "claim_type": "DAT", "importance": "CRITICAL", "current": True,
                                  "evidence": [{"source_id": "S-tmp-1", "excerpt": "VERBATIM text copied from the source",
                                                "locator": "p. 12, Table 3", "relation": "supports"}],
                                  "numbers": [{"value": 2.6, "unit": "percent of GDP", "series": "", "country": "", "period": "2025"}]}],
            "contradictions": [{"claim_text": "", "source_id": "", "note": ""}],
            "research_gaps": [""],
        },
    },
    "analyst": {
        "required": ["diagnosis", "mechanisms", "rival_explanations", "candidate_claims", "weakest_links", "falsification_tests"],
        "example": {
            "diagnosis": "",
            "mechanisms": [{"mechanism": "", "evidence_needed": ""}],
            "rival_explanations": [{"explanation": "", "evidence_for": "", "evidence_against": "", "distinguishing_test": ""}],
            "candidate_claims": [{"text": "", "claim_type": "CAU", "importance": "MATERIAL", "evidence": []}],
            "weakest_links": [""],
            "falsification_tests": [""],
        },
    },
    "registrar": {
        "required": ["claims"],
        "example": {
            "claims": [{"claim_id": "C001", "text": "", "claim_type": "DAT", "importance": "CRITICAL", "author": "agent that first proposed it",
                        "approved_wording": "wording no stronger than the evidence", "current": True,
                        "evidence": [{"source_id": "", "excerpt": "", "locator": "", "relation": "supports", "proposed_by": ""}],
                        "numbers": [], "alternatives": [], "contradictions": [], "depends_on": [], "recommendation_chain": {}}],
            "merged": [{"kept": "C001", "duplicates": ["candidate text"]}],
            "conflicts_preserved": [{"claim_ids": [], "note": "disagreement kept, not resolved by vote"}],
        },
    },
    "source_auditor": {
        "required": ["audited_claims"],
        "example": {
            "audited_claims": [{"claim_id": "C001", "status": "VERIFIED|PARTIALLY_VERIFIED|NOT_VERIFIED|CONTRADICTED|OUTDATED|SOURCE_NOT_ACCESSIBLE",
                                "source_id": "", "url": "", "excerpt": "VERBATIM supporting passage (required for VERIFIED)",
                                "locator": "", "wording_stronger_than_source": False, "recommended_wording": "", "note": ""}],
        },
    },
    "grader": {
        "required": ["grades"],
        "example": {"grades": [{"claim_id": "C001", "S": "S5", "E": "E4", "C": "C2 or null if not causal", "rationale": ""}]},
    },
    "adversarial_reviewer": {
        "required": ["overall", "issues", "would_sign_off"],
        "example": {
            "overall": "",
            "issues": [{"claim_ids": ["C005"], "category": "causal|factual|numeric|alternative|analytical|source_gap|synthesis",
                        "severity": "RED|YELLOW", "description": "exact problem", "proposed_resolution": "what evidence or rewording resolves it"}],
            "would_sign_off": False,
        },
    },
    "omission_auditor": {
        "required": ["items", "additional_omissions"],
        "example": {
            "items": [{"id": "COV-RISK", "status": "COVERED|NOT_APPLICABLE|MISSING", "claim_ids": [], "note": ""}],
            "additional_omissions": [{"description": "", "severity": "RED|YELLOW"}],
        },
    },
    "synthesizer": {
        "required": ["thesis", "findings", "dispositions"],
        "example": {
            "thesis": "strongest defensible conclusion, citing claim IDs",
            "findings": {"confirmed": ["C001"], "qualified": ["C005"], "competing": [], "unresolved": [], "rejected": []},
            "policy_implications": [{"text": "", "claim_ids": []}],
            "dispositions": [{"issue_id": "I001", "decision": "ACCEPTED|PARTIAL|REJECTED", "rationale": "evidence-based reason"}],
        },
    },
    "critic_rebuttal": {
        "required": ["verdict", "rationale"],
        "example": {"verdict": "UPHELD|WITHDRAWN", "rationale": "withdraw ONLY if the rejection cites evidence that resolves your concern"},
    },
    "adjudicator": {
        "required": ["verdict", "rationale"],
        "example": {"verdict": "FOR_CRITIC|FOR_SYNTHESIZER|ESCALATE", "rationale": ""},
    },
    "drafter": {
        "required": ["draft_markdown"],
        "example": {"draft_markdown": "# Title\n\nSentence using approved wording. [C001]\n\n## Staff Appraisal\n..."},
    },
    "substance_reviewer": {
        "required": ["issues"],
        "example": {"issues": [{"claim_ids": [], "category": "drafting", "severity": "RED|YELLOW", "description": "", "proposed_resolution": ""}]},
    },
    "structure_reviewer": {
        "required": ["issues", "score"],
        "example": {"issues": [{"claim_ids": [], "category": "drafting", "severity": "YELLOW", "description": "", "proposed_resolution": ""}],
                    "score": "0-100 for IMF drafting quality"},
    },
    "editorial_reviewer": {
        "required": ["issues", "score"],
        "example": {"issues": [{"claim_ids": [], "category": "editorial", "severity": "YELLOW", "description": "", "proposed_resolution": ""}],
                    "score": "0-100"},
    },
    "reviser": {
        "required": ["draft_markdown", "dispositions"],
        "example": {"draft_markdown": "", "dispositions": [{"issue_id": "", "decision": "ACCEPTED|REJECTED", "rationale": ""}]},
    },
    "targeted": {
        "required": ["updates"],
        "example": {"updates": [{"claim_id": "", "new_sources": [{"source_id": "", "title": "", "institution": "", "publication_date": "", "url": "", "authority_grade": ""}],
                                 "new_evidence": [{"source_id": "", "excerpt": "VERBATIM", "locator": "", "relation": "supports"}],
                                 "proposed_wording": "", "alternatives": [], "note": ""}]},
    },
}


class ContractError(ValueError):
    pass


def contract_text(role: str) -> str:
    spec = CONTRACTS[role]
    return ("Return ONLY a JSON object (no prose outside it) with at least these keys: "
            + ", ".join(spec["required"]) + ".\nShape:\n```json\n"
            + json.dumps(spec["example"], indent=2) + "\n```")


def parse(role: str, text: str) -> dict:
    """Extract and validate the JSON object in a model reply."""
    if isinstance(text, dict):
        obj = text
    else:
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
        raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ContractError(f"{role}: reply is not valid JSON ({e})") from e
    missing = [k for k in CONTRACTS[role]["required"] if k not in obj]
    if missing:
        raise ContractError(f"{role}: reply missing keys {missing}")
    return obj
