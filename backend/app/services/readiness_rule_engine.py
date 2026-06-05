from dataclasses import dataclass

from app.models.schemas import EvidenceObject, ReadinessStatus, ReadinessTaxonomyItem, SiteContext


READINESS_RULE_ENGINE_VERSION = "2026-06-05.mission-rule-matrix-v1"


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
        "reason_with_refs": "Site profile or geospatial context evidence is available for the selected mission case.",
        "next_action": "Confirm address, parcel references, coordinate precision, access, and ownership context with official records.",
    },
    "planning_regulatory_context": {
        "source_types": {"official_planning_pdf"},
        "status_with_refs": "partial",
        "reason_with_refs": "Official public or planning evidence was retrieved, but it still needs mission-specific interpretation.",
        "next_action": "Review the cited public material against the mission objective, authorization context, and any permit pathway.",
    },
    "existing_drawings": {
        "source_subtypes": {"drawing_or_plan", "survey_scan_document"},
        "status_with_refs": "partial",
        "reason_with_refs": "Drawing, plan, or survey evidence is present, but completeness and currency are not verified.",
        "next_action": "Verify drawings or survey data against the current building and request missing as-built records.",
    },
    "structural_documentation": {
        "source_subtypes": {"inspection_report"},
        "roles": {"building_record"},
        "status_with_refs": "partial",
        "reason_with_refs": "Some technical evidence may support structural review, but verified structural calculations are not confirmed.",
        "next_action": "Request structural drawings, calculations, alteration history, or schedule expert structural validation.",
    },
    "fire_safety_documentation": {
        "source_subtypes": {"fire_safety_dossier"},
        "roles": {"fire_safety_context"},
        "status_with_refs": "partial",
        "reason_with_refs": "Fire, safety, or accessibility evidence is present, but current conditions still need expert review.",
        "next_action": "Collect fire strategy, evacuation, compartmentation, accessibility, and safety documentation for expert validation.",
    },
    "building_envelope_roof": {
        "source_subtypes": {"condition_observation", "inspection_report", "photo_or_image_note"},
        "roles": {"condition_observation"},
        "content_terms": {"roof", "facade", "window", "envelope", "insulation", "durability"},
        "status_with_refs": "partial",
        "reason_with_refs": "Condition evidence relevant to facade, envelope, roof, or durability review is present.",
        "next_action": "Inspect roof, facade, openings, insulation continuity, and visible deterioration during the mission.",
    },
    "humidity_water_infiltration": {
        "source_subtypes": {"condition_observation", "inspection_report", "owner_note", "photo_or_image_note"},
        "roles": {"condition_observation"},
        "content_terms": {"humidity", "moisture", "water", "infiltration", "damp", "basement", "environmental condition"},
        "status_with_refs": "partial",
        "reason_with_refs": "Condition evidence indicates potential moisture or water-infiltration topics for review.",
        "next_action": "Inspect basement, drainage, roof water paths, facade joints, and recent moisture or environmental-condition observations.",
    },
    "mep_systems": {
        "source_subtypes": {"maintenance_record", "inspection_report", "commissioning_report", "hvac_mep_document"},
        "roles": {"maintenance_context"},
        "content_terms": {
            "electrical",
            "heating",
            "ventilation",
            "plumbing",
            "mep",
            "hvac",
            "sanitary",
            "rainwater",
            "commissioning",
        },
        "status_with_refs": "partial",
        "reason_with_refs": "Some maintenance, commissioning, HVAC, or technical-equipment evidence is present.",
        "next_action": "Collect MEP schematics, commissioning reports, maintenance records, capacity data, and mission inspection findings.",
    },
    "energy_performance": {
        "source_subtypes": {"energy_certificate_or_audit", "comfort_energy_document"},
        "roles": {"energy_context"},
        "status_with_refs": "partial",
        "reason_with_refs": "Energy, comfort, or environmental-performance evidence is present, but assumptions need validation.",
        "next_action": "Review energy certificates, comfort measurements, air-tightness data, audit findings, and mission objectives.",
    },
    "hazardous_materials": {
        "source_subtypes": {"hazardous_material_survey", "asbestos_pollutant_document"},
        "roles": {"hazardous_material_context"},
        "status_with_refs": "partial",
        "reason_with_refs": "Asbestos, pollutant, or hazardous-material evidence is present, but scope and currency must be checked.",
        "next_action": "Confirm asbestos, pollutant, lead, and contamination documentation before intrusive work or expert controls.",
    },
    "accessibility_egress": {
        "source_subtypes": {"fire_safety_dossier", "drawing_or_plan", "inspection_report"},
        "roles": {"fire_safety_context", "building_record"},
        "content_terms": {"accessibility", "egress", "evacuation", "stairs", "lift", "circulation"},
        "status_with_refs": "partial",
        "reason_with_refs": "Evidence may support accessibility or egress review, but current conditions need verification.",
        "next_action": "Check circulation, egress paths, stairs, lifts, thresholds, accessibility constraints, and control access during the mission.",
    },
    "renovation_scope_constraints": {
        "source_types": {"official_planning_pdf", "uploaded_document", "uploaded_image", "geojson"},
        "source_subtypes": {
            "environmental_authorization",
            "classified_establishment_document",
            "commissioning_report",
            "maintenance_record",
            "survey_scan_document",
            "expertise_claim_document",
        },
        "status_with_refs": "partial",
        "reason_with_refs": "Public, user-supplied, or geospatial evidence is available for mission preparation scoping.",
        "next_action": "Map authorization, access, logistics, technical, survey, and missing-document constraints before field work.",
    },
}


MISSING_REASON = "No verified case-file evidence was retrieved for this mission readiness category."
MISSING_ACTIONS = {
    "existing_drawings": "Request current drawings, as-built records, and any historic alteration plans.",
    "structural_documentation": "Request structural drawings, calculations, surveys, and alteration records for expert validation.",
    "fire_safety_documentation": "Request fire strategy, compartmentation, evacuation, accessibility, and safety records.",
    "building_envelope_roof": "Plan facade, envelope, roof, window, and durability checks during the mission.",
    "humidity_water_infiltration": "Inspect moisture-prone areas and request reports on water ingress, dampness, or environmental conditions.",
    "mep_systems": "Request MEP drawings, HVAC records, commissioning reports, maintenance logs, utility data, and system inspections.",
    "energy_performance": "Request energy certificates, comfort measurements, environmental-performance records, and audit assumptions.",
    "hazardous_materials": "Request asbestos, pollutant, and hazardous-material inventories before intrusive investigation or works.",
    "accessibility_egress": "Verify accessibility, egress, and control access conditions against the intended mission scope.",
    "renovation_scope_constraints": "Collect authorization, access, logistics, survey, technical, and missing-document constraints before field work.",
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
        item_id = f"missing_rule_{index:03d}"
        missing_items.append(
            {
                "item_id": item_id,
                "category_id": item.category_id,
                "description": item.status_reason,
                "evidence_refs": [f"ev_missing_{item_id}"],
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
            status_reason=str(rule.get("reason_with_refs", "Relevant evidence is present but needs expert review.")),
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
    seen_logical_refs: set[tuple[object, ...]] = set()
    for item in evidence:
        if item.evidence_id in refs:
            continue
        logical_ref = _logical_evidence_ref(item)
        if logical_ref in seen_logical_refs:
            continue
        if source_types and item.source_type in source_types:
            refs.append(item.evidence_id)
            seen_logical_refs.add(logical_ref)
            continue
        if source_subtypes and item.source_subtype in source_subtypes:
            refs.append(item.evidence_id)
            seen_logical_refs.add(logical_ref)
            continue
        if roles and item.evidence_role in roles:
            refs.append(item.evidence_id)
            seen_logical_refs.add(logical_ref)
            continue
        if content_terms and any(term in item.content.lower() for term in content_terms):
            refs.append(item.evidence_id)
            seen_logical_refs.add(logical_ref)
    return refs


def _logical_evidence_ref(item: EvidenceObject) -> tuple[object, ...]:
    return (
        item.source_type,
        item.source_name,
        item.source_subtype,
        item.page,
        item.locator.line_start if item.locator else item.metadata.get("line_start"),
        item.locator.line_end if item.locator else item.metadata.get("line_end"),
        " ".join(item.content.split()),
    )


def _missing_action(category_id: str, label: str) -> str:
    return MISSING_ACTIONS.get(category_id, f"Collect verified evidence for {label.lower()}.")
