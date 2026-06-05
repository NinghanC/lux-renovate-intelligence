import hashlib
import json

from app.core.paths import SAMPLE_DIR
from app.models.schemas import ReadinessTaxonomyItem
from app.services.json_store import read_json


TAXONOMY_PATH = SAMPLE_DIR / "readiness_taxonomy.json"
TAXONOMY_VERSION = "2026-06-05.readiness-taxonomy-v1"


DEFAULT_TAXONOMY = [
    {
        "category_id": "site_identity_location",
        "label": "Site identity and location",
        "description": "Address, commune, coordinates, and site identification confidence.",
    },
    {
        "category_id": "planning_regulatory_context",
        "label": "Planning and regulatory context",
        "description": "Relevant urban planning, PAP/PAG, zoning, or public planning evidence.",
    },
    {
        "category_id": "existing_drawings",
        "label": "Existing drawings and as-built records",
        "description": "Architectural plans, as-built drawings, and layout documentation.",
    },
    {
        "category_id": "structural_documentation",
        "label": "Structural documentation",
        "description": "Structural drawings, calculations, load-bearing assumptions, or survey records.",
    },
    {
        "category_id": "fire_safety_documentation",
        "label": "Fire safety documentation",
        "description": "Fire strategy, evacuation, compartmentation, and approval documentation.",
    },
    {
        "category_id": "building_envelope_roof",
        "label": "Envelope, facade, and roof",
        "description": "Facade, roof, windows, insulation, and envelope condition evidence.",
    },
    {
        "category_id": "humidity_water_infiltration",
        "label": "Humidity and water infiltration",
        "description": "Basement humidity, water ingress, drainage, and moisture observations.",
    },
    {
        "category_id": "mep_systems",
        "label": "MEP systems",
        "description": "Mechanical, electrical, plumbing, HVAC, and utilities documentation.",
    },
    {
        "category_id": "energy_performance",
        "label": "Energy performance",
        "description": "Energy certificates, performance assumptions, and renovation energy context.",
    },
    {
        "category_id": "hazardous_materials",
        "label": "Hazardous materials",
        "description": "Asbestos, lead, contaminated materials, or hazardous-material surveys.",
    },
    {
        "category_id": "accessibility_egress",
        "label": "Accessibility and egress",
        "description": "Accessibility, circulation, evacuation routes, and site access constraints.",
    },
    {
        "category_id": "renovation_scope_constraints",
        "label": "Renovation scope constraints",
        "description": "Constraints affecting renovation feasibility, permits, logistics, or investigations.",
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

