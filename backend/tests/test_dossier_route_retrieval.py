from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api import routes_dossiers
from app.main import app
from app.models.schemas import CoverageScore, Dossier, EvidenceObject, EvidenceType, RetrievedEvidence


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

    response = TestClient(app).post("/api/dossiers/generate", json={"site_id": "demo_lux_laangfur_001"})

    assert response.status_code == 200
    assert dummy_retriever.used_purposes
    assert not dummy_retriever.used_query
    assert response.json()["cache_hit"] is False


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

    response = TestClient(app).post("/api/dossiers/generate", json={"site_id": "demo_lux_laangfur_001"})

    assert response.status_code == 200
    assert response.json()["cache_hit"] is True
    assert response.json()["dossier"]["dossier_id"] == "dos_test"
    assert not dummy_retriever.used_purposes
    assert not dummy_retriever.used_query
