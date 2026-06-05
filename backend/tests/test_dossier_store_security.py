from datetime import datetime, timezone

import pytest

from app.models.schemas import CoverageScore, Dossier
from app.services import dossier_store
from app.services.dossier_store import (
    DossierNotFoundError,
    InvalidDossierIdError,
    _dossier_path,
    cache_key_for_signature,
    load_cached_dossier,
    load_dossier,
    save_dossier,
    save_dossier_cache,
)


def minimal_dossier(dossier_id: str) -> Dossier:
    return Dossier(
        dossier_id=dossier_id,
        site_context={
            "site_id": "demo_site",
            "address": "1 Demo Street",
            "commune": "Luxembourg",
            "coordinates": {"lat": 49.6116, "lon": 6.1319},
            "building_type": "mixed-use",
            "approx_year_built": 1920,
            "nearby_features": [],
            "geospatial_context": {},
            "data_quality": {
                "address_precision": "demo",
                "coordinate_precision": "approximate",
                "footprint_available": False,
                "limitations": ["Test context."],
            },
        },
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
        evidence=[],
        limitations=["Test only."],
    )


@pytest.fixture
def isolated_dossier_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(dossier_store, "DOSSIERS_DIR", tmp_path)
    monkeypatch.setattr(dossier_store, "DOSSIER_CACHE_INDEX_PATH", tmp_path / "cache_index.json")
    return tmp_path


@pytest.mark.parametrize(
    "dossier_id",
    [
        "../secrets",
        "..\\secrets",
        "/absolute/path",
        "C:\\absolute\\path",
        "dos_test.json",
        "",
    ],
)
def test_dossier_path_rejects_unsafe_ids(isolated_dossier_dir, dossier_id):
    with pytest.raises(InvalidDossierIdError):
        _dossier_path(dossier_id)


def test_load_dossier_masks_unsafe_ids_as_not_found(isolated_dossier_dir):
    with pytest.raises(DossierNotFoundError):
        load_dossier("../../etc/passwd")


def test_save_and_load_dossier_stays_inside_dossier_dir(isolated_dossier_dir):
    dossier = minimal_dossier("dos_test")

    save_dossier(dossier)
    loaded = load_dossier("dos_test")

    assert loaded.dossier_id == "dos_test"
    assert (isolated_dossier_dir / "dos_test.json").exists()


def test_cache_rejects_unsafe_cache_keys(isolated_dossier_dir):
    dossier = minimal_dossier("dos_test")

    assert load_cached_dossier("../cache") is None
    with pytest.raises(ValueError):
        save_dossier_cache("../cache", dossier, {"site_id": "demo"})


def test_cache_load_ignores_malicious_index_dossier_id(isolated_dossier_dir):
    cache_key = cache_key_for_signature({"site_id": "demo"})
    (isolated_dossier_dir / "cache_index.json").write_text(
        f'{{"{cache_key}": {{"dossier_id": "../../etc/passwd", "signature": {{}}}}}}',
        encoding="utf-8",
    )

    assert load_cached_dossier(cache_key) is None
