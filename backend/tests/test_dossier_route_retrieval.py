from datetime import datetime, timezone
import inspect

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import routes_dossiers
from app.main import app
from app.models.schemas import CoverageScore, Dossier, EvidenceObject, EvidenceType, RetrievedEvidence
from app.services.dossier_generator import PROMPT_VERSION
from app.services.evidence_validator import VALIDATOR_VERSION
from app.services.readiness_rule_engine import READINESS_RULE_ENGINE_VERSION
from app.services.semantic_reviewer import SEMANTIC_REVIEW_VERSION
from app.services.taxonomy import TAXONOMY_VERSION, taxonomy_fingerprint


AUTH_HEADERS = {"X-API-Key": "dev-demo-token-change-me"}


class DummyIngestion:
    def load_generate_chunks(self, **kwargs):
        return []

    def planning_signature(self, commune):
        return [{"commune": commune, "checksum_sha256": "planning"}]

    def uploaded_signature(self, **kwargs):
        return []


class DummyRetriever:
    def __init__(self):
        self.used_query = False
        self.used_purposes = False

    def retrieve_from_chunks(self, **kwargs):
        self.used_query = True
        return RetrievedEvidence(query=kwargs["query"], results=[evidence()])

    def retrieve_for_purposes(self, **kwargs):
        self.used_purposes = True
        return RetrievedEvidence(query="purpose-based retrieval", results=[evidence()])


class DummyGenerator:
    def generate(self, *, site_context, evidence, taxonomy):
        return Dossier(
            dossier_id="dos_test",
            site_context=site_context,
            generated_at=datetime.now(timezone.utc),
            building_summary="Test dossier.",
            public_context="Test context.",
            planning_findings=[],
            readiness_matrix=[],
            coverage_score=CoverageScore(
                coverage_score=0,
                available=0,
                partial=0,
                missing=0,
                unknown=0,
                not_applicable=0,
            ),
            missing_information_checklist=[],
            technical_risk_signals=[],
            inspection_checklist=[],
            evidence=evidence,
            limitations=["Test only."],
        )

    async def generate_async(self, *, site_context, evidence, taxonomy):
        return self.generate(site_context=site_context, evidence=evidence, taxonomy=taxonomy)


class DummySourceRegistry:
    def refresh_snapshot(self):
        return []


def evidence() -> EvidenceObject:
    return EvidenceObject(
        evidence_id="ev_test",
        evidence_type=EvidenceType.planning_document,
        source_name="Test source",
        content="Test evidence.",
    )


def test_generate_without_query_uses_purpose_based_retrieval(monkeypatch):
    dummy_retriever = DummyRetriever()
    monkeypatch.setattr(routes_dossiers, "ingestion", DummyIngestion())
    monkeypatch.setattr(routes_dossiers, "retriever", dummy_retriever)
    monkeypatch.setattr(routes_dossiers, "generator", DummyGenerator())
    monkeypatch.setattr(routes_dossiers, "source_registry", DummySourceRegistry())
    monkeypatch.setattr(routes_dossiers, "load_cached_dossier", lambda cache_key: None)
    monkeypatch.setattr(routes_dossiers, "save_dossier", lambda dossier: None)
    monkeypatch.setattr(routes_dossiers, "save_dossier_cache", lambda cache_key, dossier, signature: None)

    response = TestClient(app).post(
        "/api/dossiers/generate",
        headers=AUTH_HEADERS,
        json={"site_id": "demo_lux_laangfur_001"},
    )

    assert response.status_code == 200
    assert dummy_retriever.used_purposes
    assert not dummy_retriever.used_query
    assert response.json()["cache_hit"] is False


def test_generate_route_offloads_sync_work_from_event_loop():
    assert inspect.iscoroutinefunction(routes_dossiers.generate_dossier)


def test_generate_uses_cached_dossier_when_signature_matches(monkeypatch):
    cached = DummyGenerator().generate(
        site_context=routes_dossiers.resolver.build_context("demo_lux_laangfur_001"),
        evidence=[evidence()],
        taxonomy=[],
    )
    dummy_retriever = DummyRetriever()
    monkeypatch.setattr(routes_dossiers, "ingestion", DummyIngestion())
    monkeypatch.setattr(routes_dossiers, "retriever", dummy_retriever)
    monkeypatch.setattr(routes_dossiers, "generator", DummyGenerator())
    monkeypatch.setattr(routes_dossiers, "load_cached_dossier", lambda cache_key: cached)

    response = TestClient(app).post(
        "/api/dossiers/generate",
        headers=AUTH_HEADERS,
        json={"site_id": "demo_lux_laangfur_001"},
    )

    assert response.status_code == 200
    assert response.json()["cache_hit"] is True
    assert response.json()["dossier"]["dossier_id"] == "dos_test"
    assert not dummy_retriever.used_purposes
    assert not dummy_retriever.used_query


def test_generate_with_advanced_options_uses_custom_query_and_bypasses_cache(monkeypatch):
    class CapturingIngestion(DummyIngestion):
        def __init__(self):
            self.load_kwargs = None
            self.uploaded_signature_kwargs = None

        def load_generate_chunks(self, **kwargs):
            self.load_kwargs = kwargs
            return []

        def uploaded_signature(self, **kwargs):
            self.uploaded_signature_kwargs = kwargs
            return []

    class CapturingRetriever(DummyRetriever):
        def __init__(self):
            super().__init__()
            self.query_kwargs = None

        def retrieve_from_chunks(self, **kwargs):
            self.query_kwargs = kwargs
            return super().retrieve_from_chunks(**kwargs)

    capturing_ingestion = CapturingIngestion()
    capturing_retriever = CapturingRetriever()
    monkeypatch.setattr(routes_dossiers, "ingestion", capturing_ingestion)
    monkeypatch.setattr(routes_dossiers, "retriever", capturing_retriever)
    monkeypatch.setattr(routes_dossiers, "generator", DummyGenerator())
    monkeypatch.setattr(routes_dossiers, "source_registry", DummySourceRegistry())
    monkeypatch.setattr(routes_dossiers, "load_cached_dossier", lambda cache_key: (_ for _ in ()).throw(AssertionError("cache should be bypassed")))
    monkeypatch.setattr(routes_dossiers, "save_dossier", lambda dossier: None)
    monkeypatch.setattr(routes_dossiers, "save_dossier_cache", lambda cache_key, dossier, signature: None)

    response = TestClient(app).post(
        "/api/dossiers/generate",
        headers=AUTH_HEADERS,
        json={
            "site_id": "demo_lux_laangfur_001",
            "query": "roof condition and permit constraints",
            "include_uploaded_documents": False,
            "max_evidence": 8,
            "force_refresh": True,
        },
    )

    assert response.status_code == 200
    assert capturing_retriever.used_query
    assert not capturing_retriever.used_purposes
    assert capturing_retriever.query_kwargs["query"] == "roof condition and permit constraints"
    assert capturing_retriever.query_kwargs["limit"] == 8
    assert capturing_ingestion.load_kwargs["include_uploaded_documents"] is False
    assert capturing_ingestion.uploaded_signature_kwargs["include_uploaded_documents"] is False


def test_generate_rejects_max_evidence_outside_bounds():
    response = TestClient(app).post(
        "/api/dossiers/generate",
        headers=AUTH_HEADERS,
        json={"site_id": "demo_lux_laangfur_001", "max_evidence": 100000},
    )

    assert response.status_code == 422


def test_generate_request_model_bounds_max_evidence():
    with pytest.raises(ValidationError):
        routes_dossiers.DossierGenerateRequest(site_id="demo_lux_laangfur_001", max_evidence=0)


def test_generate_cache_signature_includes_generation_contract_versions(monkeypatch):
    monkeypatch.setattr(routes_dossiers, "ingestion", DummyIngestion())
    signature = routes_dossiers.build_generate_cache_signature(
        request=routes_dossiers.DossierGenerateRequest(site_id="demo_lux_laangfur_001"),
        commune="Luxembourg",
    )

    assert signature["cache_version"] == 3
    assert signature["generation_contract"] == {
        "prompt_version": PROMPT_VERSION,
        "readiness_rule_engine_version": READINESS_RULE_ENGINE_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "semantic_review_version": SEMANTIC_REVIEW_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy_fingerprint": taxonomy_fingerprint(),
    }
    assert "semantic_review_provider" in signature["providers"]
    assert "semantic_review_model" in signature["providers"]
