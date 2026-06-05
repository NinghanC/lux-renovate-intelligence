import json

import httpx

from app.models.schemas import Coordinates, DataQuality, EvidenceObject, EvidenceType, SiteContext
from app.services.dossier_generator import DossierGenerator, build_validated_dossier, ensure_rule_missing_evidence_available
from app.services.llm_provider import MockLLMProvider
from app.services.readiness_rule_engine import build_rule_matrix
from app.services.semantic_reviewer import SemanticReviewer
from app.services.taxonomy import load_taxonomy


class NullSourceRegistry:
    def list_sources(self):
        return None


def site_context() -> SiteContext:
    return SiteContext(
        site_id="demo_site",
        address="1 Demo Street",
        commune="Luxembourg",
        coordinates=Coordinates(lat=49.6116, lon=6.1319),
        building_type="mixed-use",
        approx_year_built=1920,
        data_quality=DataQuality(
            address_precision="demo",
            coordinate_precision="approximate",
            footprint_available=False,
            limitations=["Demo test context."],
        ),
    )


def evidence() -> list[EvidenceObject]:
    return [
        EvidenceObject(
            evidence_id="ev_planning",
            evidence_type=EvidenceType.planning_document,
            source_id="src_planning",
            source_type="official_planning_pdf",
            authority_level="municipal_official",
            source_name="Planning PDF",
            page=1,
            chunk_id="chunk_001",
            content="Planning context for the selected site.",
        ),
        EvidenceObject(
            evidence_id="ev_site",
            evidence_type=EvidenceType.site_profile,
            source_id="src_site",
            source_type="site_profile",
            authority_level="demo_data",
            source_name="Demo site profile",
            content="Site identity and coordinate context.",
        ),
    ]


def dossier_fixture():
    context = site_context()
    items = evidence()
    taxonomy = load_taxonomy()
    rule_matrix = build_rule_matrix(site_context=context, evidence=items, taxonomy=taxonomy)
    generation_evidence = ensure_rule_missing_evidence_available(items, rule_matrix)
    draft_result = MockLLMProvider().generate_draft(
        system_prompt="system",
        user_prompt=json.dumps(
            {
                "site_context": context.model_dump(),
                "taxonomy": [item.model_dump() for item in taxonomy],
                "evidence": [
                    {"evidence_id": item.evidence_id, "source_type": item.source_type}
                    for item in generation_evidence
                ],
                "readiness_matrix_locked": [item.model_dump() for item in rule_matrix],
            },
            default=str,
        ),
    )
    dossier = build_validated_dossier(
        site_context=context,
        evidence=generation_evidence,
        taxonomy=taxonomy,
        draft=draft_result.draft,
        usage=draft_result.usage,
        rule_matrix=rule_matrix,
        source_registry=None,
    )
    return context, generation_evidence, rule_matrix, dossier


def test_semantic_reviewer_disabled_returns_report_only_disabled_review():
    context, items, rule_matrix, dossier = dossier_fixture()
    reviewer = SemanticReviewer(provider="disabled")

    result = reviewer.review(
        site_context=context,
        dossier=dossier,
        evidence=items,
        rule_matrix=rule_matrix,
    )

    assert result.review.enabled is False
    assert result.review.status == "disabled"
    assert result.review.blocking is False
    assert result.usage is None


def test_dossier_generator_attaches_disabled_semantic_review_by_default():
    context = site_context()
    items = evidence()
    taxonomy = load_taxonomy()
    generator = DossierGenerator(
        llm_provider=MockLLMProvider(),
        source_registry=NullSourceRegistry(),
        semantic_reviewer=SemanticReviewer(provider="disabled"),
    )

    dossier = generator.generate(site_context=context, evidence=items, taxonomy=taxonomy)

    assert dossier.semantic_review is not None
    assert dossier.semantic_review.status == "disabled"
    assert dossier.semantic_review_usage is None


def test_semantic_reviewer_parses_structured_response_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "review-model"
        content = {
            "enabled": True,
            "status": "warnings",
            "blocking": False,
            "overclaiming_detected": True,
            "absence_to_risk_violation": False,
            "unsupported_claims": ["The summary needs stronger evidence for one interpretation."],
            "forbidden_claim_warnings": [],
            "grounding_warnings": ["One checklist item should cite derived missing-information evidence."],
            "review_notes": ["Report-only semantic review completed."],
            "error_summary": None,
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(content)}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                },
            },
        )

    context, items, rule_matrix, dossier = dossier_fixture()
    reviewer = SemanticReviewer(
        provider="openai_compatible",
        api_key="token",
        base_url="https://example.test",
        model="review-model",
        response_format="json_object",
        transport=httpx.MockTransport(handler),
    )

    result = reviewer.review(
        site_context=context,
        dossier=dossier,
        evidence=items,
        rule_matrix=rule_matrix,
    )

    assert result.review.enabled is True
    assert result.review.status == "warnings"
    assert result.review.blocking is False
    assert result.review.reviewer_provider == "openai_compatible"
    assert result.review.reviewer_model == "review-model"
    assert result.review.overclaiming_detected is True
    assert result.usage is not None
    assert result.usage.external_llm_called is True
    assert result.usage.total_tokens_reported == 120


def test_semantic_reviewer_failure_does_not_block_generation():
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(500, json={"error": "failed"})

    context, items, rule_matrix, dossier = dossier_fixture()
    reviewer = SemanticReviewer(
        provider="openai_compatible",
        api_key="token",
        base_url="https://example.test",
        model="review-model",
        transport=httpx.MockTransport(handler),
    )

    result = reviewer.review(
        site_context=context,
        dossier=dossier,
        evidence=items,
        rule_matrix=rule_matrix,
    )

    assert result.review.enabled is True
    assert result.review.status == "failed"
    assert result.review.blocking is False
    assert result.review.error_summary == "Semantic reviewer failed. Generation output was not blocked."
    assert result.usage is None
