import json
from datetime import datetime, timezone
from uuid import uuid4

from app.models.schemas import (
    Dossier,
    DossierDraft,
    EvidenceObject,
    EvidenceType,
    MissingInformationItem,
    ReadinessTaxonomyItem,
    SiteContext,
)
from app.services.coverage_calculator import calculate_coverage
from app.services.evidence_validator import (
    validate_claim_support,
    validate_evidence_source_integrity,
    validate_evidence_refs,
    validate_forbidden_claims,
    validate_matrix_evidence_requirements,
    validate_matrix_matches_rule_output,
    validate_taxonomy_complete,
)
from app.services.llm_provider import LLMProvider, MockLLMProvider, create_llm_provider
from app.services.readiness_rule_engine import RuleMatrixItem, build_rule_matrix, build_rule_missing_items
from app.services.source_registry import SourceRegistry


SYSTEM_PROMPT = """You are a bounded renovation-readiness assistant for SECO-style engineering preparation.
Use only the provided site context, taxonomy, and evidence. Do not use outside facts.
Do not make final structural safety, fire safety, legal, planning-compliance, energy, or occupancy decisions.
Return only one valid JSON object matching the requested schema. Do not wrap it in Markdown. Every finding and checklist item must cite evidence_refs.
All human-facing narrative fields must be written in English. Keep IDs, enum values, source names, page numbers, and evidence IDs unchanged.
The readiness matrix status and evidence_refs are rule-derived and locked.
Do not change readiness_matrix category_id, label, status, or evidence_refs.
Only write human-readable summaries, next actions, findings, risk signals, checklist items, and limitations."""


def build_user_prompt(
    *,
    site_context: SiteContext,
    evidence: list[EvidenceObject],
    taxonomy: list[ReadinessTaxonomyItem],
    rule_matrix: list[RuleMatrixItem],
) -> str:
    schema_hint = {
        "building_summary": "string",
        "planning_findings": [
            {
                "finding_id": "finding_001",
                "title": "string",
                "summary": "string",
                "evidence_refs": ["ev_..."],
                "source_document": "string or null",
                "page": "integer or null",
                "chunk_id": "string or null",
            }
        ],
        "readiness_matrix": [
            {
                "category_id": "copy exactly from readiness_matrix_locked",
                "label": "copy exactly from readiness_matrix_locked",
                "status": "copy exactly from readiness_matrix_locked",
                "summary": "string",
                "evidence_refs": "copy exactly from readiness_matrix_locked",
                "recommended_next_action": "string",
            }
        ],
        "missing_information_checklist": [
            {
                "item_id": "missing_001",
                "category_id": "taxonomy category id",
                "description": "string",
                "evidence_refs": ["ev_..."],
                "recommended_next_action": "string",
            }
        ],
        "technical_risk_signals": [
            {
                "signal_id": "signal_001",
                "title": "string",
                "description": "uncertainty requiring human review, not a final judgement",
                "evidence_refs": ["ev_..."],
                "priority": "high | medium | low",
            }
        ],
        "inspection_checklist": [
            {
                "item_id": "check_001",
                "task": "string",
                "reason": "string",
                "evidence_refs": ["ev_..."],
                "priority": "high | medium | low",
            }
        ],
        "limitations": ["at least one limitation"],
    }
    compact_evidence = [
        {
            "evidence_id": item.evidence_id,
            "type": item.evidence_type,
            "source_id": item.source_id,
            "source_type": item.source_type,
            "source_subtype": item.source_subtype,
            "modality": item.modality,
            "authority_level": item.authority_level,
            "evidence_role": item.evidence_role,
            "source_name": item.source_name,
            "page": item.page,
            "chunk_id": item.chunk_id,
            "supports": item.supports,
            "parser": item.parser,
            "content": item.content[:1800],
            "metadata": item.metadata,
        }
        for item in evidence
    ]
    return json.dumps(
        {
            "site_context": site_context.model_dump(),
            "taxonomy": [item.model_dump() for item in taxonomy],
            "readiness_matrix_locked": [item.model_dump() for item in rule_matrix],
            "allowed_evidence_ids": [item.evidence_id for item in evidence],
            "evidence": compact_evidence,
            "required_schema": schema_hint,
            "requirements": [
                "Copy every readiness_matrix_locked item into readiness_matrix exactly once.",
                "Do not change readiness_matrix category_id, label, status, or evidence_refs.",
                "Use readiness_matrix_locked status_reason to write each readiness_matrix summary.",
                "Use readiness_matrix_locked recommended_next_action_seed to write each readiness_matrix recommended_next_action.",
                "For missing categories, recommended_next_action must be specific and non-empty.",
                "Do not claim the building is safe, compliant, approved, or free of risk.",
                "Make inspection_checklist useful for old-building renovation preparation.",
                "Return at least 5 inspection_checklist items.",
                "Each inspection_checklist item must cite at least one evidence_ref.",
                "Each planning_finding and technical_risk_signal item must cite at least one evidence_ref.",
                "Every evidence_ref must be copied exactly from allowed_evidence_ids. Do not cite site_context fields, taxonomy fields, source paths, or chunk IDs without the ev_ prefix.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


class DossierGenerator:
    def __init__(
        self,
        llm_provider: LLMProvider | MockLLMProvider | None = None,
        source_registry: SourceRegistry | None = None,
    ):
        self.llm_provider = llm_provider or create_llm_provider()
        self.source_registry = source_registry or SourceRegistry()

    def generate(
        self,
        *,
        site_context: SiteContext,
        evidence: list[EvidenceObject],
        taxonomy: list[ReadinessTaxonomyItem],
    ) -> Dossier:
        rule_matrix = build_rule_matrix(
            site_context=site_context,
            evidence=evidence,
            taxonomy=taxonomy,
        )
        generation_evidence = ensure_rule_missing_evidence_available(evidence, rule_matrix)
        draft = self.llm_provider.generate_draft(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(
                site_context=site_context,
                evidence=generation_evidence,
                taxonomy=taxonomy,
                rule_matrix=rule_matrix,
            ),
        )
        return build_validated_dossier(
            site_context=site_context,
            evidence=generation_evidence,
            taxonomy=taxonomy,
            draft=draft,
            rule_matrix=rule_matrix,
            source_registry=self.source_registry,
        )


def build_validated_dossier(
    *,
    site_context: SiteContext,
    evidence: list[EvidenceObject],
    taxonomy: list[ReadinessTaxonomyItem],
    draft: DossierDraft,
    rule_matrix: list[RuleMatrixItem] | None = None,
    source_registry: SourceRegistry | None = None,
) -> Dossier:
    if rule_matrix is not None:
        evidence = ensure_rule_missing_evidence_available(evidence, rule_matrix)
    validate_taxonomy_complete(draft)
    normalize_draft_evidence_refs(draft, evidence)
    if rule_matrix is not None:
        validate_matrix_matches_rule_output(draft, rule_matrix)
        ensure_rule_missing_information(draft, rule_matrix)
    validate_evidence_refs(draft, evidence)
    validate_matrix_evidence_requirements(draft)
    sources = source_registry.list_sources() if source_registry else None
    validate_evidence_source_integrity(evidence, sources)
    validate_claim_support(draft, evidence, sources)
    validate_forbidden_claims(draft)
    evidence_with_missing = evidence + build_missing_information_evidence(draft, evidence)
    coverage = calculate_coverage(draft.readiness_matrix)
    public_context = (
        f"{site_context.commune} demo context with {len(evidence)} retrieved evidence item(s). "
        "The dossier is evidence-backed and does not represent a final engineering decision."
    )
    dossier = Dossier(
        dossier_id=f"dos_{uuid4().hex[:12]}",
        site_context=site_context,
        generated_at=datetime.now(timezone.utc),
        building_summary=draft.building_summary,
        public_context=public_context,
        planning_findings=draft.planning_findings,
        readiness_matrix=draft.readiness_matrix,
        coverage_score=coverage,
        missing_information_checklist=draft.missing_information_checklist,
        technical_risk_signals=draft.technical_risk_signals,
        inspection_checklist=draft.inspection_checklist,
        evidence=evidence_with_missing,
        limitations=draft.limitations,
    )
    validate_evidence_source_integrity(evidence_with_missing, sources)
    validate_forbidden_claims(dossier)
    return dossier


def normalize_draft_evidence_refs(draft: DossierDraft, evidence: list[EvidenceObject]) -> None:
    known = {item.evidence_id for item in evidence}
    by_chunk = {item.chunk_id: item.evidence_id for item in evidence if item.chunk_id}

    def normalize(refs: list[str]) -> list[str]:
        normalized: list[str] = []
        for ref in refs:
            candidate = ref
            if candidate in known:
                normalized.append(candidate)
                continue
            if candidate.startswith("ev_ev_") and candidate[3:] in known:
                normalized.append(candidate[3:])
                continue
            if candidate in by_chunk:
                normalized.append(by_chunk[candidate])
                continue
            if candidate.startswith("ev_") and candidate[3:] in by_chunk:
                normalized.append(by_chunk[candidate[3:]])
                continue
            normalized.append(candidate)
        return list(dict.fromkeys(normalized))

    for finding in draft.planning_findings:
        finding.evidence_refs = normalize(finding.evidence_refs)
    for item in draft.readiness_matrix:
        item.evidence_refs = normalize(item.evidence_refs)
    for item in draft.missing_information_checklist:
        item.evidence_refs = [ref for ref in normalize(item.evidence_refs) if ref in known]
    for signal in draft.technical_risk_signals:
        signal.evidence_refs = normalize(signal.evidence_refs)
    for item in draft.inspection_checklist:
        item.evidence_refs = normalize(item.evidence_refs)


def ensure_rule_missing_information(draft: DossierDraft, rule_matrix: list[RuleMatrixItem]) -> None:
    existing_by_category = {item.category_id: item for item in draft.missing_information_checklist}
    for item in build_rule_missing_items(rule_matrix):
        category_id = str(item["category_id"])
        existing = existing_by_category.get(category_id)
        if existing:
            for ref in item["evidence_refs"]:
                if isinstance(ref, str) and ref not in existing.evidence_refs:
                    existing.evidence_refs.append(ref)
            continue
        missing_item = MissingInformationItem.model_validate(item)
        draft.missing_information_checklist.append(missing_item)
        existing_by_category[category_id] = missing_item


def ensure_rule_missing_evidence_available(
    evidence: list[EvidenceObject],
    rule_matrix: list[RuleMatrixItem],
) -> list[EvidenceObject]:
    known = {item.evidence_id for item in evidence}
    rule_missing_items = [MissingInformationItem.model_validate(item) for item in build_rule_missing_items(rule_matrix)]
    derived = [
        item
        for item in build_missing_information_evidence_for_items(rule_missing_items, evidence)
        if item.evidence_id not in known
    ]
    return [*evidence, *derived]


def build_missing_information_evidence(
    draft: DossierDraft,
    source_evidence: list[EvidenceObject],
) -> list[EvidenceObject]:
    return build_missing_information_evidence_for_items(draft.missing_information_checklist, source_evidence)


def build_missing_information_evidence_for_items(
    missing_items: list[MissingInformationItem],
    source_evidence: list[EvidenceObject],
) -> list[EvidenceObject]:
    known_refs = {item.evidence_id for item in source_evidence}
    derived: list[EvidenceObject] = []
    for index, item in enumerate(missing_items, start=1):
        evidence_id = f"ev_missing_{item.item_id or index}"
        if evidence_id in known_refs:
            continue
        supporting_refs = [ref for ref in item.evidence_refs if ref in known_refs and ref != evidence_id]
        content = (
            f"Missing information evidence for category '{item.category_id}': {item.description} "
            f"Recommended next action: {item.recommended_next_action}"
        )
        derived.append(
            EvidenceObject(
                evidence_id=evidence_id,
                evidence_type=EvidenceType.derived_missing_information,
                source_id="src_system_derived_missing_information",
                source_type="derived",
                source_subtype="missing_information",
                modality="derived_text",
                authority_level="system_derived",
                evidence_role="missing_information",
                source_name="Missing information evidence",
                content=content,
                supports=[item.category_id],
                metadata={
                    "category_id": item.category_id,
                    "missing_item_id": item.item_id,
                    "supporting_evidence_refs": supporting_refs,
                    "derived": True,
                },
                confidence="medium",
            )
        )
    return derived
