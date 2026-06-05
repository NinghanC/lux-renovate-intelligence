from app.models.schemas import Coordinates, DataQuality, EvidenceObject, EvidenceType, SiteContext
from app.services.dossier_generator import build_user_prompt, build_validated_dossier
from app.services.llm_provider import LLMProvider, MockLLMProvider
from app.services.taxonomy import load_taxonomy


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


def test_mock_llm_provider_generates_validated_dossier():
    context = site_context()
    items = evidence()
    taxonomy = load_taxonomy()
    draft = MockLLMProvider().generate_draft(
        system_prompt="system",
        user_prompt=build_user_prompt(site_context=context, evidence=items, taxonomy=taxonomy),
    )
    dossier = build_validated_dossier(
        site_context=context,
        evidence=items,
        taxonomy=taxonomy,
        draft=draft,
        source_registry=None,
    )

    assert dossier.building_summary.startswith("Demo-mode dossier")
    assert len(dossier.inspection_checklist) >= 5
    assert {item.category_id for item in dossier.readiness_matrix} == {
        item.category_id for item in taxonomy
    }


def test_real_llm_provider_requires_configuration():
    provider = LLMProvider(api_key=None, base_url="https://example.test", model="demo-model")

    assert provider.configured is False
