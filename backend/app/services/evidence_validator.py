import re

from app.models.schemas import Dossier, DossierDraft, EvidenceObject
from app.services.taxonomy import taxonomy_ids


class ValidationFailure(ValueError):
    pass


FORBIDDEN_PATTERNS = [
    r"\bis structurally safe\b",
    r"\bstructurally sound\b",
    r"\bno structural risk\b",
    r"\bfire[- ]?safety compliant\b",
    r"\bfully compliant with fire\b",
    r"\blegally compliant\b",
    r"\bplanning compliant\b",
    r"\bsafe for occupancy\b",
    r"\bapproved for construction\b",
    r"结构安全(?:已|已经)?确认",
    r"消防合规(?:已|已经)?确认",
    r"符合法规(?:要求)?$",
    r"可以直接施工",
    r"不存在风险",
]


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
    known = {item.evidence_id for item in evidence}
    refs: set[str] = set()
    for finding in dossier.planning_findings:
        refs.update(finding.evidence_refs)
    for item in dossier.readiness_matrix:
        refs.update(item.evidence_refs)
    for item in dossier.missing_information_checklist:
        refs.update(item.evidence_refs)
    for signal in dossier.technical_risk_signals:
        refs.update(signal.evidence_refs)
    for item in dossier.inspection_checklist:
        refs.update(item.evidence_refs)
    missing = sorted(ref for ref in refs if ref not in known)
    if missing:
        raise ValidationFailure(f"Dossier references unknown evidence IDs: {missing}")


def validate_forbidden_claims(dossier: Dossier | DossierDraft) -> None:
    text = dossier.model_dump_json()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            raise ValidationFailure(f"Forbidden final engineering/legal claim detected: {pattern}")


def validate_dossier(dossier: Dossier, evidence: list[EvidenceObject]) -> None:
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
    validate_forbidden_claims(dossier)

