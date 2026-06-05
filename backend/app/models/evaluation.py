from typing import Literal

from pydantic import BaseModel, Field


EvaluationMode = Literal["mock", "real"]


class EvaluationInputs(BaseModel):
    site_id: str
    query: str | None = None
    uploaded_documents: list[str] = Field(default_factory=list)
    generation_mode: EvaluationMode = "mock"
    include_uploaded_documents: bool = True
    max_evidence: int = 12


class RetrievalExpectations(BaseModel):
    min_evidence: int = 0
    required_source_types: list[str] = Field(default_factory=list)
    required_supports: list[str] = Field(default_factory=list)
    max_site_mismatch_count: int = 0


class MatrixCategoryExpectation(BaseModel):
    status: str | None = None
    requires_evidence: bool = False
    requires_next_action: bool = False
    forbidden_statuses: list[str] = Field(default_factory=list)


class GenerationExpectations(BaseModel):
    min_inspection_items: int = 5
    require_evidence_refs: bool = True
    forbid_final_claims: bool = True
    locked_matrix_statuses: bool = True
    limitations_required: bool = True


class DossierExpectations(BaseModel):
    coverage_score_matches_matrix: bool = True
    missing_information_evidence_coverage: float = 1.0


class EvaluationExpectations(BaseModel):
    retrieval: RetrievalExpectations = Field(default_factory=RetrievalExpectations)
    matrix: dict[str, MatrixCategoryExpectation] = Field(default_factory=dict)
    generation: GenerationExpectations = Field(default_factory=GenerationExpectations)
    dossier: DossierExpectations = Field(default_factory=DossierExpectations)


class EvaluationCase(BaseModel):
    case_id: str
    inputs: EvaluationInputs
    expectations: EvaluationExpectations


class AbsenceToRiskExpectation(BaseModel):
    category_id: str
    missing_status_required: bool = True
    forbidden_meanings: list[str] = Field(default_factory=list)
    allowed_meanings_any: list[str] = Field(default_factory=list)


class SemanticExpectations(BaseModel):
    absence_to_risk: AbsenceToRiskExpectation
    required_limitations: list[str] = Field(default_factory=list)


class SemanticEvaluationCase(BaseModel):
    case_id: str
    inputs: EvaluationInputs
    semantic_expectations: SemanticExpectations


class EvaluationFailure(BaseModel):
    metric: str
    expected: object | None = None
    actual: object | None = None
    message: str


class EvaluationCaseResult(BaseModel):
    case_id: str
    passed: bool
    failures: list[EvaluationFailure] = Field(default_factory=list)
    metrics: dict[str, object] = Field(default_factory=dict)


class EvaluationRunReport(BaseModel):
    run_id: str
    mode: EvaluationMode
    passed: bool
    summary: dict[str, int]
    cases: list[EvaluationCaseResult]
