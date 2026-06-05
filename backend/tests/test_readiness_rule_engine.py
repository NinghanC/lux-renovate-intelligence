from app.models.schemas import Coordinates, DataQuality, EvidenceObject, EvidenceType, SiteContext
from app.services.readiness_rule_engine import build_rule_matrix
from app.services.taxonomy import load_taxonomy


def site_context() -> SiteContext:
    return SiteContext(
        site_id="demo_site",
        address="1 Demo Street",
        commune="Luxembourg",
        coordinates=Coordinates(lat=49.6116, lon=6.1319),
        data_quality=DataQuality(
            address_precision="demo",
            coordinate_precision="approximate",
            footprint_available=False,
            limitations=["Demo context."],
        ),
    )


def evidence_item(
    evidence_id: str,
    *,
    source_type: str | None = None,
    source_subtype: str | None = None,
    evidence_role: str | None = None,
    content: str = "Evidence content.",
) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.uploaded_document,
        source_name="Evidence",
        source_type=source_type,
        source_subtype=source_subtype,
        evidence_role=evidence_role,
        content=content,
    )


def matrix_by_category(evidence: list[EvidenceObject]):
    matrix = build_rule_matrix(
        site_context=site_context(),
        evidence=evidence,
        taxonomy=load_taxonomy(),
    )
    return {item.category_id: item for item in matrix}


def test_site_profile_and_geojson_make_site_identity_available():
    matrix = matrix_by_category(
        [
            evidence_item("ev_site", source_type="site_profile"),
            evidence_item("ev_geo", source_type="geojson"),
        ]
    )

    assert matrix["site_identity_location"].status == "available"
    assert matrix["site_identity_location"].evidence_refs == ["ev_site", "ev_geo"]


def test_official_planning_evidence_makes_planning_partial():
    matrix = matrix_by_category([evidence_item("ev_plan", source_type="official_planning_pdf")])

    assert matrix["planning_regulatory_context"].status == "partial"
    assert matrix["planning_regulatory_context"].evidence_refs == ["ev_plan"]


def test_uploaded_drawing_makes_existing_drawings_partial():
    matrix = matrix_by_category([evidence_item("ev_drawing", source_subtype="drawing_or_plan")])

    assert matrix["existing_drawings"].status == "partial"
    assert matrix["existing_drawings"].evidence_refs == ["ev_drawing"]


def test_owner_note_does_not_make_structural_documentation_available():
    matrix = matrix_by_category(
        [
            evidence_item(
                "ev_owner",
                source_subtype="owner_note",
                evidence_role="uploaded_context",
                content="Owner note mentions old beams and possible cracks.",
            )
        ]
    )

    assert matrix["structural_documentation"].status == "missing"
    assert matrix["structural_documentation"].evidence_refs == []
