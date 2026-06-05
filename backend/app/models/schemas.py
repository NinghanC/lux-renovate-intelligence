from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.usage import TokenUsage


ReadinessStatus = Literal["available", "partial", "missing", "unknown", "not_applicable"]
Priority = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]
SourceType = Literal[
    "official_planning_pdf",
    "site_profile",
    "uploaded_document",
    "uploaded_image",
    "geojson",
    "derived",
]
SourceAuthority = Literal[
    "municipal_official",
    "demo_data",
    "user_supplied",
    "open_geospatial",
    "system_derived",
    "unknown",
]


class EvidenceType(str, Enum):
    site_profile = "site_profile"
    geospatial = "geospatial"
    planning_document = "planning_document"
    uploaded_document = "uploaded_document"
    uploaded_image = "uploaded_image"
    derived_missing_information = "derived_missing_information"
    synthetic_historical_case = "synthetic_historical_case"


class Coordinates(BaseModel):
    lat: float
    lon: float


class DemoSite(BaseModel):
    site_id: str
    display_name: str
    input_address: str
    commune: str
    coordinates: Coordinates
    building_type: str | None = None
    approx_year_built: int | None = None
    description: str
    available_public_sources: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)


class DataQuality(BaseModel):
    address_precision: str
    coordinate_precision: str
    footprint_available: bool | None = None
    limitations: list[str] = Field(default_factory=list)


class SiteContext(BaseModel):
    site_id: str
    address: str
    commune: str
    coordinates: Coordinates
    building_type: str | None = None
    approx_year_built: int | None = None
    nearby_features: list[str] = Field(default_factory=list)
    geospatial_context: dict[str, Any] = Field(default_factory=dict)
    data_quality: DataQuality


class PlanningChunk(BaseModel):
    chunk_id: str
    document_id: str
    source_id: str | None = None
    document_name: str
    document_type: str
    commune: str
    page: int
    section_title: str | None = None
    text: str
    source_path: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceRecord(BaseModel):
    source_id: str
    display_name: str
    source_type: SourceType
    source_subtype: str | None = None
    modality: str | None = None
    authority: SourceAuthority = "unknown"
    commune: str | None = None
    language: str | None = None
    original_url: str | None = None
    source_page_url: str | None = None
    local_path: str | None = None
    checksum_sha256: str | None = None
    page_count: int | None = None
    parser: str | None = None
    status: str = "registered"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceRecordPublic(BaseModel):
    source_id: str
    display_name: str
    source_type: SourceType
    source_subtype: str | None = None
    modality: str | None = None
    authority: SourceAuthority = "unknown"
    commune: str | None = None
    language: str | None = None
    original_url: str | None = None
    source_page_url: str | None = None
    page_count: int | None = None
    parser: str | None = None
    status: str = "registered"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceLocator(BaseModel):
    page: int | None = None
    chunk_id: str | None = None


class EvidenceObject(BaseModel):
    evidence_id: str
    evidence_type: EvidenceType
    source_id: str | None = None
    source_type: SourceType | None = None
    source_subtype: str | None = None
    modality: str | None = None
    authority_level: SourceAuthority | None = None
    evidence_role: str | None = None
    source_name: str
    source_path: str | None = None
    source_url: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    locator: EvidenceLocator | None = None
    supports: list[str] = Field(default_factory=list)
    parser: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: Confidence = "medium"
    score: float | None = None


class RetrievedEvidence(BaseModel):
    query: str
    results: list[EvidenceObject]
    limitations: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    document_id: str
    source_id: str | None = None
    document_type: str
    source_subtype: str | None = None
    modality: str | None = None
    filename: str
    chunks_created: int
    chunks: list[PlanningChunk]


class SiteGeoJsonResponse(BaseModel):
    site_id: str
    radius_m: float
    geojson: dict[str, Any]


class CoverageScore(BaseModel):
    coverage_score: int
    available: int
    partial: int
    missing: int
    unknown: int
    not_applicable: int


class ReadinessTaxonomyItem(BaseModel):
    category_id: str
    label: str
    description: str


class ReadinessMatrixItem(BaseModel):
    category_id: str
    label: str
    status: ReadinessStatus
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_next_action: str


class Finding(BaseModel):
    finding_id: str
    title: str
    summary: str
    evidence_refs: list[str]
    source_document: str | None = None
    page: int | None = None
    chunk_id: str | None = None


class MissingInformationItem(BaseModel):
    item_id: str
    category_id: str
    description: str
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_next_action: str


class RiskSignal(BaseModel):
    signal_id: str
    title: str
    description: str
    evidence_refs: list[str] = Field(default_factory=list)
    priority: Priority


class ChecklistItem(BaseModel):
    item_id: str
    task: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    priority: Priority


class DossierDraft(BaseModel):
    building_summary: str
    planning_findings: list[Finding] = Field(default_factory=list)
    readiness_matrix: list[ReadinessMatrixItem]
    missing_information_checklist: list[MissingInformationItem] = Field(default_factory=list)
    technical_risk_signals: list[RiskSignal] = Field(default_factory=list)
    inspection_checklist: list[ChecklistItem] = Field(default_factory=list, min_length=5)
    limitations: list[str]

    @field_validator("limitations")
    @classmethod
    def limitations_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("limitations must not be empty")
        return value


class Dossier(BaseModel):
    dossier_id: str
    site_context: SiteContext
    generated_at: datetime
    building_summary: str
    public_context: str
    planning_findings: list[Finding]
    readiness_matrix: list[ReadinessMatrixItem]
    coverage_score: CoverageScore
    missing_information_checklist: list[MissingInformationItem]
    technical_risk_signals: list[RiskSignal]
    inspection_checklist: list[ChecklistItem]
    evidence: list[EvidenceObject]
    limitations: list[str]
    usage: TokenUsage | None = None


class DossierGenerateRequest(BaseModel):
    site_id: str
    query: str | None = None
    include_uploaded_documents: bool = True
    max_evidence: int = 12
    force_refresh: bool = False


class DossierGenerateResponse(BaseModel):
    dossier: Dossier
    cache_hit: bool = False


class ApiError(BaseModel):
    detail: str
    code: str
    hints: list[str] = Field(default_factory=list)
