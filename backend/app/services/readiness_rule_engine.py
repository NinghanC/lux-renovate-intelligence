from dataclasses import dataclass

from app.models.schemas import EvidenceObject, ReadinessStatus, ReadinessTaxonomyItem, SiteContext


@dataclass(frozen=True)
class RuleMatrixItem:
    category_id: str
    label: str
    status: ReadinessStatus
    evidence_refs: list[str]
    status_reason: str
    recommended_next_action_seed: str

    def model_dump(self) -> dict[str, object]:
        return {
            "category_id": self.category_id,
            "label": self.label,
            "status": self.status,
            "evidence_refs": self.evidence_refs,
            "status_reason": self.status_reason,
            "recommended_next_action_seed": self.recommended_next_action_seed,
        }


CATEGORY_RULES: dict[str, dict[str, object]] = {
    "site_identity_location": {
        "source_types": {"site_profile", "geojson"},
        "status_with_refs": "available",
        "reason_with_refs": "Site profile or geospatial context evidence is available for the selected demo site.",
        "next_action": "Confirm address, parcel references, coordinate precision, and ownership context with official records.",
    },
    "planning_regulatory_context": {
        "source_types": {"official_planning_pdf"},
        "status_with_refs": "partial",
        "reason_with_refs": "Official planning evidence was retrieved, but it still needs project-specific interpretation.",
        "next_action": "Review the cited planning material against the intended renovation scope and permit pathway.",
    },
    "existing_drawings": {
        "source_subtypes": {"drawing_or_plan"},
        "status_with_refs": "partial",
        "reason_with_refs": "Drawing or plan evidence was uploaded or retrieved, but completeness and currency are not verified.",
        "next_action": "Verify drawings against the current building and request missing as-built records.",
    },
    "structural_documentation": {
        "source_subtypes": {"inspection_report"},
        "roles": {"building_record"},
        "status_with_refs": "partial",
        "reason_with_refs": "Some technical evidence may support structural review, but verified structural calculations are not confirmed.",
        "next_action": "Request structural drawings, calculations, alteration history, or schedule a structural survey.",
    },
    "fire_safety_documentation": {
        "source_subtypes": {"fire_safety_dossier"},
        "roles": {"fire_safety_context"},
        "status_with_refs": "partial",
        "reason_with_refs": "Fire-safety evidence is present, but approvals and current conditions still need review.",
        "next_action": "Collect fire strategy, evacuation, compartmentation, and approval documentation for human review.",
    },
    "building_envelope_roof": {
        "source_subtypes": {"condition_observation", "inspection_report", "photo_or_image_note"},
        "roles": {"condition_observation"},
        "content_terms": {"roof", "facade", "window", "envelope", "insulation"},
        "status_with_refs": "partial",
        "reason_with_refs": "Condition evidence relevant to envelope, facade, or roof review is present.",
        "next_action": "Inspect roof, facade, openings, insulation continuity, and visible deterioration on site.",
    },
    "humidity_water_infiltration": {
        "source_subtypes": {"condition_observation", "inspection_report", "owner_note", "photo_or_image_note"},
        "roles": {"condition_observation"},
        "content_terms": {"humidity", "moisture", "water", "infiltration", "damp", "basement"},
        "status_with_refs": "partial",
        "reason_with_refs": "Condition evidence indicates potential moisture or water-infiltration topics for review.",
        "next_action": "Inspect basement, drainage, roof water paths, facade joints, and recent moisture observations.",
    },
    "mep_systems": {
        "source_subtypes": {"maintenance_record", "inspection_report"},
        "roles": {"maintenance_context"},
        "content_terms": {"electrical", "heating", "ventilation", "plumbing", "mep", "hvac"},
        "status_with_refs": "partial",
        "reason_with_refs": "Some maintenance or technical evidence related to MEP systems is present.",
        "next_action": "Collect MEP schematics, maintenance records, capacity data, and inspection findings.",
    },
    "energy_performance": {
        "source_subtypes": {"energy_certificate_or_audit"},
        "roles": {"energy_context"},
        "status_with_refs": "partial",
        "reason_with_refs": "Energy certificate or audit evidence is present, but renovation assumptions need validation.",
        "next_action": "Review energy certificates, audit findings, envelope assumptions, and renovation targets.",
    },
    "hazardous_materials": {
        "source_subtypes": {"hazardous_material_survey"},
        "roles": {"hazardous_material_context"},
        "status_with_refs": "partial",
        "reason_with_refs": "Hazardous-material survey evidence is present, but scope and currency must be checked.",
        "next_action": "Confirm asbestos, lead, and contamination surveys before invasive renovation work.",
    },
    "accessibility_egress": {
        "source_subtypes": {"fire_safety_dossier", "drawing_or_plan", "inspection_report"},
        "roles": {"fire_safety_context", "building_record"},
        "content_terms": {"accessibility", "egress", "evacuation", "stairs", "lift", "circulation"},
        "status_with_refs": "partial",
        "reason_with_refs": "Evidence may support accessibility or egress review, but current conditions need verification.",
        "next_action": "Check circulation, egress paths, stairs, lifts, thresholds, and accessibility constraints on site.",
    },
    "renovation_scope_constraints": {
        "source_types": {"official_planning_pdf", "uploaded_document", "uploaded_image"},
        "status_with_refs": "partial",
        "reason_with_refs": "Planning or user-supplied evidence is available for early renovation-scope scoping.",
        "next_action": "Map planning, access, logistics, technical, and missing-document constraints before design work.",
    },
}


MISSING_REASON = "No verified evidence was retrieved for this readiness category."
MISSING_ACTIONS = {
    "existing_drawings": "Request current drawings, as-built records, and any historic alteration plans.",
    "structural_documentation": "Request structural drawings, calculations, surveys, and alteration records.",
    "fire_safety_documentation": "Request fire strategy, compartmentation, evacuation, and approval records.",
    "building_envelope_roof": "Schedule envelope, facade, roof, window, and insulation condition inspection.",
    "humidity_water_infiltration": "Inspect moisture-prone areas and request reports on water ingress or dampness.",
    "mep_systems": "Request MEP drawings, maintenance logs, utility data, and system inspections.",
    "energy_performance": "Request energy certificates, audits, and renovation energy assumptions.",
    "hazardous_materials": "Request hazardous-material surveys before intrusive investigation or works.",
    "accessibility_egress": "Verify accessibility and egress conditions against the intended renovation use.",
    "renovation_scope_constraints": "Collect scope, permit, logistics, and technical constraints before design decisions.",
}


def build_rule_matrix(
    *,
    site_context: SiteContext,
    evidence: list[EvidenceObject],
    taxonomy: list[ReadinessTaxonomyItem],
) -> list[RuleMatrixItem]:
    del site_context
    return [_evaluate_category(item, evidence) for item in taxonomy]


def build_rule_missing_items(rule_matrix: list[RuleMatrixItem]) -> list[dict[str, object]]:
    missing_items: list[dict[str, object]] = []
    for index, item in enumerate(rule_matrix, start=1):
        if item.status not in {"missing", "unknown"}:
            continue
        missing_items.append(
            {
                "item_id": f"missing_rule_{index:03d}",
                "category_id": item.category_id,
                "description": item.status_reason,
                "evidence_refs": item.evidence_refs,
                "recommended_next_action": item.recommended_next_action_seed,
            }
        )
    return missing_items


def _evaluate_category(taxonomy_item: ReadinessTaxonomyItem, evidence: list[EvidenceObject]) -> RuleMatrixItem:
    category_id = taxonomy_item.category_id
    rule = CATEGORY_RULES.get(category_id, {})
    refs = _matching_refs(evidence, rule)
    if refs:
        return RuleMatrixItem(
            category_id=category_id,
            label=taxonomy_item.label,
            status=rule.get("status_with_refs", "partial"),  # type: ignore[arg-type]
            evidence_refs=refs[:3],
            status_reason=str(rule.get("reason_with_refs", "Relevant evidence is present but needs human review.")),
            recommended_next_action_seed=str(rule.get("next_action", _missing_action(category_id, taxonomy_item.label))),
        )
    return RuleMatrixItem(
        category_id=category_id,
        label=taxonomy_item.label,
        status="missing",
        evidence_refs=[],
        status_reason=MISSING_REASON,
        recommended_next_action_seed=_missing_action(category_id, taxonomy_item.label),
    )


def _matching_refs(evidence: list[EvidenceObject], rule: dict[str, object]) -> list[str]:
    source_types = set(rule.get("source_types", set()))
    source_subtypes = set(rule.get("source_subtypes", set()))
    roles = set(rule.get("roles", set()))
    content_terms = {str(term).lower() for term in set(rule.get("content_terms", set()))}
    refs: list[str] = []
    for item in evidence:
        if item.evidence_id in refs:
            continue
        if source_types and item.source_type in source_types:
            refs.append(item.evidence_id)
            continue
        if source_subtypes and item.source_subtype in source_subtypes:
            refs.append(item.evidence_id)
            continue
        if roles and item.evidence_role in roles:
            refs.append(item.evidence_id)
            continue
        if content_terms and any(term in item.content.lower() for term in content_terms):
            refs.append(item.evidence_id)
    return refs


def _missing_action(category_id: str, label: str) -> str:
    return MISSING_ACTIONS.get(category_id, f"Collect verified evidence for {label.lower()}.")
