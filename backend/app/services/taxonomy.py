import hashlib
import json

from app.core.paths import SAMPLE_DIR
from app.models.schemas import ReadinessTaxonomyItem
from app.services.json_store import read_json


TAXONOMY_PATH = SAMPLE_DIR / "readiness_taxonomy.json"
TAXONOMY_VERSION = "2026-06-05.mission-readiness-taxonomy-v1"


DEFAULT_TAXONOMY = [
    {
        "category_id": "site_identity_location",
        "label": "Site and building identity",
        "description": "Address, commune, coordinates, building identity, and case-file confidence.",
    },
    {
        "category_id": "planning_regulatory_context",
        "label": "Public, regulatory, and authorization context",
        "description": "Public planning, authorization, classified-establishment, and regulatory context evidence.",
    },
    {
        "category_id": "existing_drawings",
        "label": "Drawings, layouts, and case-file geometry",
        "description": "Architectural plans, as-built drawings, layouts, survey records, and geometry documentation.",
    },
    {
        "category_id": "structural_documentation",
        "label": "Structural documentation",
        "description": "Structural drawings, calculations, load-bearing assumptions, or survey records.",
    },
    {
        "category_id": "fire_safety_documentation",
        "label": "Fire, safety, and accessibility documentation",
        "description": "Fire strategy, evacuation, compartmentation, accessibility, and safety documentation.",
    },
    {
        "category_id": "building_envelope_roof",
        "label": "Facade, envelope, roof, and durability context",
        "description": "Facade, roof, windows, insulation, durability, and envelope condition evidence.",
    },
    {
        "category_id": "humidity_water_infiltration",
        "label": "Moisture, water infiltration, and environmental condition indicators",
        "description": "Basement humidity, water ingress, drainage, moisture observations, and environmental condition indicators.",
    },
    {
        "category_id": "mep_systems",
        "label": "Technical equipment, HVAC, sanitary, electrical, and rainwater systems",
        "description": "Mechanical, electrical, plumbing, HVAC, sanitary, rainwater, utilities, and commissioning documentation.",
    },
    {
        "category_id": "energy_performance",
        "label": "Energy, comfort, and environmental performance evidence",
        "description": "Energy certificates, comfort measurements, air-tightness, environmental performance, and audit context.",
    },
    {
        "category_id": "hazardous_materials",
        "label": "Asbestos, pollutants, and hazardous-material documentation",
        "description": "Asbestos, pollutants, lead, contaminated materials, or hazardous-material surveys.",
    },
    {
        "category_id": "accessibility_egress",
        "label": "Accessibility and egress",
        "description": "Accessibility, circulation, evacuation routes, control access, and site access constraints.",
    },
    {
        "category_id": "renovation_scope_constraints",
        "label": "Required expert checks, controls, measurements, or inspections",
        "description": "Mission-critical controls, measurements, scans, expert checks, site investigations, and follow-up actions.",
    },
]


def load_taxonomy() -> list[ReadinessTaxonomyItem]:
    if TAXONOMY_PATH.exists():
        return [ReadinessTaxonomyItem.model_validate(row) for row in read_json(TAXONOMY_PATH)]
    return [ReadinessTaxonomyItem.model_validate(row) for row in DEFAULT_TAXONOMY]


def taxonomy_ids() -> set[str]:
    return {item.category_id for item in load_taxonomy()}


def taxonomy_fingerprint() -> str:
    payload = [item.model_dump(mode="json") for item in load_taxonomy()]
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

