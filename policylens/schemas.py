from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnswerResponse(BaseModel):
    """Structured model response for ordinary policy questions."""

    answer: str = Field(description="Plain-language answer based only on supplied policy evidence.")
    has_sufficient_evidence: bool = Field(
        description="False when the retrieved policy passages do not establish the answer."
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Only IDs of supplied evidence chunks that directly support the answer.",
    )
    uncertainty: str | None = Field(
        default=None, description="What is missing or ambiguous, or null when not applicable."
    )


class CoverageAnalysis(BaseModel):
    coverage_summary: str = Field(description="What the retrieved wording says may be covered.")
    relevant_exclusions: str = Field(description="Relevant exclusions or state that none were found.")
    conditions_and_limits: str = Field(description="Conditions, limits, and requirements that apply.")
    deductible_or_excess: str = Field(description="Applicable deductible/excess or not stated.")
    practical_interpretation: str = Field(description="Cautious explanation for the user's scenario.")
    insufficient_evidence: bool = Field(description="Whether the policy evidence is incomplete.")
    missing_information: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ClaimDocumentItem(BaseModel):
    document_name: str
    purpose: str
    requirement_level: Literal["required", "conditional", "not_stated"]
    when_needed: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class ClaimChecklist(BaseModel):
    summary: str
    items: list[ClaimDocumentItem] = Field(default_factory=list)
    missing_user_information: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
