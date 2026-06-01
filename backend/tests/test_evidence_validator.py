import pytest

from app.models.schemas import (
    ChecklistItem,
    DossierDraft,
    EvidenceObject,
    EvidenceType,
    MissingInformationItem,
    ReadinessMatrixItem,
    SourceRecord,
)
from app.services.dossier_generator import build_missing_information_evidence
from app.services.dossier_generator import normalize_draft_evidence_refs
from app.services.evidence_validator import (
    ValidationFailure,
    validate_evidence_refs,
    validate_evidence_source_integrity,
    validate_forbidden_claims,
    validate_claim_support,
    validate_taxonomy_complete,
)
from app.services.taxonomy import load_taxonomy


def evidence() -> list[EvidenceObject]:
    return [
        EvidenceObject(
            evidence_id="ev_001",
            evidence_type=EvidenceType.planning_document,
            source_name="Planning PDF",
            content="Planning context text",
        )
    ]


def source(source_id="src_001", source_type="official_planning_pdf", page_count=2) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        display_name="Planning PDF",
        source_type=source_type,
        authority="municipal_official" if source_type == "official_planning_pdf" else "user_supplied",
        page_count=page_count,
    )


def matrix_items(refs=None) -> list[ReadinessMatrixItem]:
    refs = refs or []
    return [
        ReadinessMatrixItem(
            category_id=category.category_id,
            label=category.label,
            status="unknown",
            summary="Requires evidence review.",
            evidence_refs=refs,
            recommended_next_action="Collect and verify supporting documents.",
        )
        for category in load_taxonomy()
    ]


def draft(refs=None, summary="Evidence is limited and needs human review.") -> DossierDraft:
    checklist = [
        ChecklistItem(
            item_id=f"check_{index}",
            task="Verify renovation preparation evidence on site.",
            reason="The MVP requires human verification of retrieved evidence and missing records.",
            evidence_refs=[],
            priority="medium",
        )
        for index in range(5)
    ]
    return DossierDraft(
        building_summary=summary,
        planning_findings=[],
        readiness_matrix=matrix_items(refs),
        missing_information_checklist=[],
        technical_risk_signals=[],
        inspection_checklist=checklist,
        limitations=["This is not a final engineering decision."],
    )


def test_taxonomy_complete_accepts_all_categories():
    validate_taxonomy_complete(draft())


def test_unknown_evidence_refs_are_rejected():
    with pytest.raises(ValidationFailure):
        validate_evidence_refs(draft(refs=["ev_missing"]), evidence())


def test_evidence_source_integrity_rejects_page_outside_source_range():
    items = [
        EvidenceObject(
            evidence_id="ev_001",
            evidence_type=EvidenceType.planning_document,
            source_id="src_001",
            source_name="Planning PDF",
            page=3,
            content="Planning context text",
        )
    ]
    with pytest.raises(ValidationFailure):
        validate_evidence_source_integrity(items, [source(page_count=2)])


def test_planning_claim_requires_official_planning_source():
    items = [
        EvidenceObject(
            evidence_id="ev_001",
            evidence_type=EvidenceType.uploaded_document,
            source_id="src_upload",
            source_name="Owner note",
            content="Owner note text",
        )
    ]
    dossier_draft = draft()
    for item in dossier_draft.readiness_matrix:
        if item.category_id == "planning_regulatory_context":
            item.status = "partial"
            item.evidence_refs = ["ev_001"]
    with pytest.raises(ValidationFailure):
        validate_claim_support(dossier_draft, items, [source("src_upload", source_type="uploaded_document")])


def test_missing_information_items_become_derived_evidence():
    dossier_draft = draft()
    dossier_draft.missing_information_checklist = [
        MissingInformationItem(
            item_id="missing_001",
            category_id="structural_documentation",
            description="Structural documentation was not found in retrieved evidence.",
            evidence_refs=["ev_001"],
            recommended_next_action="Request structural drawings or schedule a structural survey.",
        )
    ]
    generated = build_missing_information_evidence(dossier_draft, evidence())

    assert generated
    assert generated[0].evidence_type == EvidenceType.derived_missing_information
    assert generated[0].source_name == "Missing information evidence"


def test_chunk_refs_are_normalized_to_evidence_ids():
    dossier_draft = draft()
    dossier_draft.inspection_checklist[0].evidence_refs = ["ev_ev_001"]
    normalize_draft_evidence_refs(dossier_draft, evidence())

    assert dossier_draft.inspection_checklist[0].evidence_refs == ["ev_001"]


@pytest.mark.parametrize(
    "claim",
    [
        "The building is structurally safe.",
        "The project is fire-safety compliant.",
        "The site is legally compliant.",
    ],
)
def test_forbidden_final_claims_are_rejected(claim: str):
    with pytest.raises(ValidationFailure):
        validate_forbidden_claims(draft(summary=claim))
