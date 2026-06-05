from typing import Literal

from pydantic import BaseModel, Field


SemanticReviewStatus = Literal["disabled", "passed", "warnings", "failed"]


class SemanticReview(BaseModel):
    enabled: bool
    status: SemanticReviewStatus
    blocking: bool = False
    reviewer_provider: str | None = None
    reviewer_model: str | None = None
    overclaiming_detected: bool = False
    absence_to_risk_violation: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)
    forbidden_claim_warnings: list[str] = Field(default_factory=list)
    grounding_warnings: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
    error_summary: str | None = None
