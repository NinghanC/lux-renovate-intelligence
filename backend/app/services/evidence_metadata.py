import json
from pathlib import Path


UPLOAD_METADATA_SUFFIX = ".meta.json"

UPLOAD_SUBTYPES: set[str] = {
    "condition_observation",
    "inspection_report",
    "drawing_or_plan",
    "maintenance_record",
    "energy_certificate_or_audit",
    "fire_safety_dossier",
    "hazardous_material_survey",
    "owner_note",
    "photo_or_image_note",
    "unknown_upload",
}

UPLOAD_SUBTYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("drawing_or_plan", ("drawing", "plan", "layout", "as-built", "as built", "floor plan", "blueprint")),
    ("inspection_report", ("inspection", "survey", "engineer", "technical report", "assessment")),
    ("energy_certificate_or_audit", ("energy", "performance", "epc", "certificate", "audit", "efficiency")),
    ("fire_safety_dossier", ("fire", "incendie", "egress", "evacuation", "compartmentation")),
    ("hazardous_material_survey", ("asbestos", "hazardous", "pollution", "contamination", "lead paint")),
    ("condition_observation", ("condition", "observation", "crack", "humidity", "moisture", "roof", "facade")),
    ("maintenance_record", ("maintenance", "repair", "service", "invoice", "work order")),
    ("photo_or_image_note", ("photo", "image", "scan", "picture", "visual")),
    ("owner_note", ("owner", "note", "memo", "reported", "tenant")),
]


def normalize_upload_subtype(source_subtype: str | None, filename: str, text: str = "") -> str:
    if source_subtype:
        normalized = source_subtype.strip().lower()
        if normalized in UPLOAD_SUBTYPES:
            return normalized
        raise ValueError(f"Unsupported upload document type '{source_subtype}'.")
    return infer_upload_subtype(filename, text)


def infer_upload_subtype(filename: str, text: str = "") -> str:
    haystack = f"{filename} {text[:4000]}".lower()
    for subtype, keywords in UPLOAD_SUBTYPE_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return subtype
    return "unknown_upload"


def upload_metadata_path(path: Path) -> Path:
    return path.with_name(f"{path.name}{UPLOAD_METADATA_SUFFIX}")


def is_upload_metadata_path(path: Path) -> bool:
    return path.name.endswith(UPLOAD_METADATA_SUFFIX)


def read_upload_metadata(path: Path) -> dict:
    metadata_path = upload_metadata_path(path)
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_upload_metadata(path: Path, metadata: dict) -> None:
    upload_metadata_path(path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def modality_for_path(path: Path | str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".txt", ".md", ".markdown"}:
        return "text"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        return "image"
    if suffix in {".json", ".geojson"}:
        return "geojson"
    return "unknown"


def evidence_role_for_document_type(document_type: str, source_subtype: str | None = None) -> str:
    if document_type in {"PAG", "PAP"}:
        return "planning_context"
    if document_type == "uploaded":
        if source_subtype in {"condition_observation", "inspection_report"}:
            return "condition_observation"
        if source_subtype == "drawing_or_plan":
            return "building_record"
        if source_subtype == "maintenance_record":
            return "maintenance_context"
        if source_subtype == "energy_certificate_or_audit":
            return "energy_context"
        if source_subtype == "fire_safety_dossier":
            return "fire_safety_context"
        if source_subtype == "hazardous_material_survey":
            return "hazardous_material_context"
        return "uploaded_context"
    return "document_context"
