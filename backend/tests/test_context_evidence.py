from app.services.context_evidence import build_context_evidence
from app.services.geospatial import GeoJsonService
from app.services.site_resolver import SiteResolver


def test_context_evidence_adds_site_profile_and_geo_refs():
    context = SiteResolver().build_context("demo_lux_laangfur_001")
    geojson = GeoJsonService().build_site_geojson(
        site_id=context.site_id,
        coordinates=context.coordinates,
    )

    evidence = build_context_evidence(context, geojson)

    assert [item.evidence_type for item in evidence]
    assert {item.source_type for item in evidence} == {"site_profile", "geojson"}
    assert all("site_identity_location" in item.supports for item in evidence)
