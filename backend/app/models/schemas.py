from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ReadinessStatus = Literal["available", "partial", "missing", "unknown", "not_applicable"]
Priority = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]


class EvidenceType(str, Enum):
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
    document_name: str
    document_type: str
    commune: str
    page: int
    section_title: str | None = None
    text: str
    source_path: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceObject(BaseModel):
    evidence_id: str
    evidence_type: EvidenceType
    source_name: str
    source_path: str | None = None
    source_url: str | None = None
    page: int | None = None
    chunk_id: str | None = None
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
    document_type: str
    filename: str
    chunks_created: int
    chunks: list[PlanningChunk]


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


class DossierGenerateRequest(BaseModel):
    site_id: str
    query: str | None = None
    include_uploaded_documents: bool = True
    max_evidence: int = 8


class DossierGenerateResponse(BaseModel):
    dossier: Dossier


class ApiError(BaseModel):
    detail: str
    code: str
    hints: list[str] = Field(default_factory=list)
