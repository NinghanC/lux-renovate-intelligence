import re

from app.models.schemas import Dossier, DossierDraft, EvidenceObject, SourceRecord
from app.services.readiness_rule_engine import RuleMatrixItem
from app.services.taxonomy import taxonomy_ids


VALIDATOR_VERSION = "2026-06-05.mission-claims-v1"


class ValidationFailure(ValueError):
    pass


FORBIDDEN_PATTERNS = [
    r"\bis structurally safe\b",
    r"\bstructurally sound\b",
    r"\bno structural risk\b",
    r"\bfree of structural risk\b",
    r"\bfire[- ]?safety compliant\b",
    r"\bfully compliant with fire\b",
    r"\blegally compliant\b",
    r"\bplanning compliant\b",
    r"\bcompliant with planning law\b",
    r"\bsafe for occupancy\b",
    r"\bapproved for construction\b",
    r"\bapproved for renovation\b",
    r"\bapproved for operation\b",
    r"\bauthorized for operation\b",
    r"\bautorisation satisfied\b",
    r"\bcommodo[- ]?incommodo compliant\b",
    r"\bITM compliant\b",
    r"\bSNSFP compliant\b",
    r"\bAEV compliant\b",
    r"\benvironmentally compliant\b",
    r"\basbestos[- ]?free\b",
    r"\bpollutant[- ]?free\b",
    r"\bno asbestos (?:present|detected|found|identified|risk|concern|issue|hazard)\b",
    r"\bno pollutants (?:present|detected|found|identified|risk|concern|issue|hazard)\b",
    r"\bHVAC compliant\b",
    r"\bHVAC is defective\b",
    r"\bno further inspection required\b",
    r"\bconforme au droit\b",
    r"\bconforme aux regles\b",
    r"\bbrandschutzkonform\b",
    r"\brechtlich konform\b",
    r"\bvoldoet aan de regelgeving\b",
]

MISSING_DOCUMENT_CONTEXT_TERMS = {
    "documentation",
    "document",
    "dossier",
    "evidence",
    "inventory",
    "record",
    "report",
    "assessment",
    "certificate",
    "statement",
    "claim",
    "approval",
    "authorization",
}

PLANNING_CATEGORIES = {
    "planning_regulatory_context",
}

HARD_ENGINEERING_CATEGORIES = {
    "structural_documentation",
    "fire_safety_documentation",
    "hazardous_materials",
}


def validate_taxonomy_complete(draft: DossierDraft) -> None:
    expected = taxonomy_ids()
    actual = {item.category_id for item in draft.readiness_matrix}
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise ValidationFailure(f"Readiness matrix is missing taxonomy categories: {sorted(missing)}")
    if extra:
        raise ValidationFailure(f"Readiness matrix contains unknown categories: {sorted(extra)}")


def validate_evidence_refs(dossier: Dossier | DossierDraft, evidence: list[EvidenceObject]) -> None:
    missing_required_refs: list[str] = []
    known = {item.evidence_id for item in evidence}
    refs: set[str] = set()
    for finding in dossier.planning_findings:
        if not finding.evidence_refs:
            missing_required_refs.append(f"planning_findings.{finding.finding_id}")
        refs.update(finding.evidence_refs)
    for item in dossier.readiness_matrix:
        refs.update(item.evidence_refs)
    for item in dossier.missing_information_checklist:
        refs.update(item.evidence_refs)
    for signal in dossier.technical_risk_signals:
        if not signal.evidence_refs:
            missing_required_refs.append(f"technical_risk_signals.{signal.signal_id}")
        refs.update(signal.evidence_refs)
    for item in dossier.inspection_checklist:
        if not item.evidence_refs:
            missing_required_refs.append(f"inspection_checklist.{item.item_id}")
        refs.update(item.evidence_refs)
    if missing_required_refs:
        raise ValidationFailure(f"Dossier items require evidence_refs: {missing_required_refs}")
    missing = sorted(ref for ref in refs if ref not in known)
    if missing:
        raise ValidationFailure(f"Dossier references unknown evidence IDs: {missing}")


def validate_matrix_evidence_requirements(dossier: Dossier | DossierDraft) -> None:
    missing_refs = [
        item.category_id
        for item in dossier.readiness_matrix
        if item.status in {"available", "partial"} and not item.evidence_refs
    ]
    if missing_refs:
        raise ValidationFailure(
            f"Readiness matrix available/partial categories require evidence refs: {missing_refs}"
        )


def validate_matrix_matches_rule_output(draft: DossierDraft, rule_matrix: list[RuleMatrixItem]) -> None:
    expected_order = [item.category_id for item in rule_matrix]
    actual_order = [item.category_id for item in draft.readiness_matrix]
    if actual_order != expected_order:
        raise ValidationFailure("Readiness matrix does not match rule-derived category order.")
    expected_by_category = {item.category_id: item for item in rule_matrix}
    for item in draft.readiness_matrix:
        expected = expected_by_category[item.category_id]
        if item.label != expected.label:
            raise ValidationFailure(f"LLM changed rule-derived label for '{item.category_id}'.")
        if item.status != expected.status:
            raise ValidationFailure(f"LLM changed rule-derived status for '{item.category_id}'.")
        if item.phase != expected.phase:
            raise ValidationFailure(f"LLM changed rule-derived phase for '{item.category_id}'.")
        if item.criticality != expected.criticality:
            raise ValidationFailure(f"LLM changed rule-derived criticality for '{item.category_id}'.")
        if item.evidence_refs != expected.evidence_refs:
            raise ValidationFailure(f"LLM changed rule-derived evidence refs for '{item.category_id}'.")


def validate_evidence_source_integrity(
    evidence: list[EvidenceObject],
    sources: list[SourceRecord] | None,
) -> None:
    if sources is None:
        return
    source_by_id = {source.source_id: source for source in sources}
    for item in evidence:
        if not item.source_id:
            raise ValidationFailure(f"Evidence item '{item.evidence_id}' is missing source_id.")
        source = source_by_id.get(item.source_id)
        if source is None:
            raise ValidationFailure(
                f"Evidence item '{item.evidence_id}' references unknown source_id '{item.source_id}'."
            )
        if item.page is not None and source.page_count is not None:
            if item.page < 1 or item.page > source.page_count:
                raise ValidationFailure(
                    f"Evidence item '{item.evidence_id}' page {item.page} is outside source page range 1..{source.page_count}."
                )


def validate_claim_support(
    dossier: Dossier | DossierDraft,
    evidence: list[EvidenceObject],
    sources: list[SourceRecord] | None,
) -> None:
    if sources is None:
        return
    evidence_by_id = {item.evidence_id: item for item in evidence}
    source_by_id = {source.source_id: source for source in sources}

    for item in dossier.readiness_matrix:
        cited_sources = [
            source_by_id.get(evidence_by_id[ref].source_id or "")
            for ref in item.evidence_refs
            if ref in evidence_by_id
        ]
        cited_types = {source.source_type for source in cited_sources if source is not None}
        if item.category_id in PLANNING_CATEGORIES and item.status in {"available", "partial"}:
            if "official_planning_pdf" not in cited_types:
                raise ValidationFailure(
                    f"Category '{item.category_id}' needs at least one official planning source."
                )
        if item.category_id in HARD_ENGINEERING_CATEGORIES and item.status == "available":
            if cited_types and cited_types <= {"uploaded_document", "uploaded_image", "derived"}:
                raise ValidationFailure(
                    f"Category '{item.category_id}' cannot be marked available using only uploaded or derived evidence."
                )


def validate_forbidden_claims(dossier: Dossier | DossierDraft) -> None:
    if isinstance(dossier, Dossier):
        text = dossier.model_dump_json(exclude={"usage", "semantic_review", "semantic_review_usage"})
    else:
        text = dossier.model_dump_json()
    for pattern in FORBIDDEN_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if _is_missing_document_context(text, match.start(), match.end()):
                continue
            raise ValidationFailure(f"Forbidden final engineering/legal claim detected: {pattern}")


def _is_missing_document_context(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 45) : start].lower()
    claim = text[start:end].lower()
    after = text[end : min(len(text), end + 90)].lower()
    missing_before = re.search(r"\b(no|missing|without|lack(?:s|ing)?|unavailable|not available|not found|not retrieved)\b", before)
    missing_in_claim = re.search(r"\bno\b", claim)
    document_after = any(term in after for term in MISSING_DOCUMENT_CONTEXT_TERMS)
    missing_after = re.search(r"\b(was|were|is|are)?\s*(not found|not available|missing|unavailable|not retrieved)\b", after)
    return bool(((missing_before or missing_in_claim) and document_after) or (document_after and missing_after))


def validate_dossier(
    dossier: Dossier,
    evidence: list[EvidenceObject],
    sources: list[SourceRecord] | None = None,
) -> None:
    validate_taxonomy_complete(
        DossierDraft(
            building_summary=dossier.building_summary,
            planning_findings=dossier.planning_findings,
            readiness_matrix=dossier.readiness_matrix,
            missing_information_checklist=dossier.missing_information_checklist,
            technical_risk_signals=dossier.technical_risk_signals,
            inspection_checklist=dossier.inspection_checklist,
            limitations=dossier.limitations,
        )
    )
    validate_evidence_refs(dossier, evidence)
    validate_matrix_evidence_requirements(dossier)
    validate_evidence_source_integrity(evidence, sources)
    validate_claim_support(dossier, evidence, sources)
    validate_forbidden_claims(dossier)
