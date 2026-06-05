import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import Dossier, EvidenceObject, SiteContext
from app.models.semantic_review import SemanticReview
from app.models.usage import TokenUsage
from app.services.llm_provider import extract_json_object, normalize_message_content
from app.services.readiness_rule_engine import RuleMatrixItem
from app.services.retry_policy import post_with_retries
from app.services.token_monitor import build_real_usage


SEMANTIC_REVIEW_VERSION = "2026-06-05.semantic-reviewer-v1"
logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """You are a report-only semantic reviewer for renovation-readiness dossiers.
You are not the generator, not an engineer of record, and not an authority.
Return only one valid JSON object matching the requested schema.
Review whether the dossier overclaims, converts missing evidence into risk conclusions, or uses unsupported interpretations.
Do not rewrite the dossier. Do not approve or reject engineering, safety, legal, planning, energy, or occupancy status.
Use English only. Avoid quoting prohibited phrases verbatim; describe them generically instead."""


class SemanticReviewResult(BaseModel):
    review: SemanticReview
    usage: TokenUsage | None = None


class SemanticReviewer:
    """Optional OpenAI-compatible semantic quality reviewer."""

    def __init__(
        self,
        provider: str = settings.semantic_review_provider,
        api_key: str | None = settings.semantic_review_api_key,
        base_url: str | None = settings.semantic_review_base_url,
        model: str | None = settings.semantic_review_model,
        response_format: str | None = settings.semantic_review_response_format,
        timeout_seconds: int = settings.semantic_review_timeout_seconds,
        transport: httpx.BaseTransport | None = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.response_format = response_format
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @property
    def enabled(self) -> bool:
        return self.provider != "disabled"

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.api_key and self.base_url and self.model)

    def review(
        self,
        *,
        site_context: SiteContext,
        dossier: Dossier,
        evidence: list[EvidenceObject],
        rule_matrix: list[RuleMatrixItem],
    ) -> SemanticReviewResult:
        if not self.enabled:
            return SemanticReviewResult(review=disabled_semantic_review())
        if not self.configured:
            return SemanticReviewResult(
                review=failed_semantic_review(
                    provider=self.provider,
                    model=self.model,
                    message="Semantic reviewer is enabled but not configured.",
                )
            )

        user_prompt = build_review_prompt(
            site_context=site_context,
            dossier=dossier,
            evidence=evidence,
            rule_matrix=rule_matrix,
        )
        endpoint = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = post_with_retries(client.post, endpoint, json=payload, headers=headers)
                response.raise_for_status()
            response_payload = response.json()
            response_text = normalize_message_content(response_payload["choices"][0]["message"]["content"])
            review = SemanticReview.model_validate(json.loads(extract_json_object(response_text)))
            review.enabled = True
            review.reviewer_provider = self.provider
            review.reviewer_model = self.model
            review.blocking = False
            usage = build_real_usage(
                provider=self.provider,
                model=self.model,
                system_prompt=REVIEW_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_text=response_text,
                response_payload=response_payload,
            )
            return SemanticReviewResult(review=review, usage=usage)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Semantic reviewer failed: %s", exc)
            return SemanticReviewResult(
                review=failed_semantic_review(
                    provider=self.provider,
                    model=self.model,
                    message="Semantic reviewer failed. Generation output was not blocked.",
                )
            )


def create_semantic_reviewer() -> SemanticReviewer:
    return SemanticReviewer()


def disabled_semantic_review() -> SemanticReview:
    return SemanticReview(
        enabled=False,
        status="disabled",
        blocking=False,
        reviewer_provider="disabled",
        review_notes=["Semantic review is disabled."],
    )


def failed_semantic_review(*, provider: str | None, model: str | None, message: str) -> SemanticReview:
    return SemanticReview(
        enabled=True,
        status="failed",
        blocking=False,
        reviewer_provider=provider,
        reviewer_model=model,
        error_summary=message,
        review_notes=[message],
    )


def build_review_prompt(
    *,
    site_context: SiteContext,
    dossier: Dossier,
    evidence: list[EvidenceObject],
    rule_matrix: list[RuleMatrixItem],
) -> str:
    compact_evidence = [
        {
            "evidence_id": item.evidence_id,
            "source_type": item.source_type,
            "evidence_type": item.evidence_type.value,
            "source_name": item.source_name,
            "page": item.page,
            "supports": item.supports,
            "content": item.content[:900],
        }
        for item in evidence
    ]
    dossier_payload = dossier.model_dump(
        mode="json",
        exclude={
            "evidence",
            "usage",
            "semantic_review",
            "semantic_review_usage",
        }
    )
    schema_hint = {
        "enabled": True,
        "status": "passed | warnings | failed",
        "blocking": False,
        "overclaiming_detected": False,
        "absence_to_risk_violation": False,
        "unsupported_claims": [],
        "forbidden_claim_warnings": [],
        "grounding_warnings": [],
        "review_notes": [],
        "error_summary": None,
    }
    return json.dumps(
        {
            "site_context": site_context.model_dump(),
            "dossier": dossier_payload,
            "rule_matrix_locked": [item.model_dump() for item in rule_matrix],
            "evidence": compact_evidence,
            "required_schema": schema_hint,
            "semantic_rules": [
                "Flag overclaiming when the dossier treats limited evidence as a final engineering, safety, legal, planning, energy, or occupancy conclusion.",
                "Flag absence_to_risk_violation when missing documentation is presented as proof of a real defect or real hazard.",
                "Flag unsupported_claims when a finding, checklist item, risk signal, or summary has no plausible support in cited evidence.",
                "Checklist items may cite missing-information evidence when they are framed as requests to collect or verify documents.",
                "Warnings are report-only and must not rewrite dossier content.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
