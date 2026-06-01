export type ReadinessStatus = "available" | "partial" | "missing" | "unknown" | "not_applicable";
export type Priority = "high" | "medium" | "low";

export interface Coordinates {
  lat: number;
  lon: number;
}

export interface DemoSite {
  site_id: string;
  display_name: string;
  input_address: string;
  commune: string;
  coordinates: Coordinates;
  building_type: string | null;
  approx_year_built: number | null;
  description: string;
  available_public_sources: string[];
  source_notes: string[];
}

export interface SiteContext {
  site_id: string;
  address: string;
  commune: string;
  coordinates: Coordinates;
  building_type: string | null;
  approx_year_built: number | null;
  nearby_features: string[];
  geospatial_context: Record<string, unknown>;
  data_quality: {
    address_precision: string;
    coordinate_precision: string;
    footprint_available: boolean | null;
    limitations: string[];
  };
}

export interface EvidenceObject {
  evidence_id: string;
  evidence_type: string;
  source_id: string | null;
  source_name: string;
  source_path: string | null;
  source_url: string | null;
  page: number | null;
  chunk_id: string | null;
  locator: {
    page: number | null;
    chunk_id: string | null;
  } | null;
  supports: string[];
  parser: string | null;
  content: string;
  metadata: Record<string, unknown>;
  confidence: "high" | "medium" | "low";
  score: number | null;
}

export interface GeoJsonFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: {
    feature_id?: string;
    name?: string;
    feature_type?: string;
    site_id?: string;
    distance_m?: number;
    source_id?: string;
  };
}

export interface SiteGeoJsonResponse {
  site_id: string;
  radius_m: number;
  geojson: {
    type: "FeatureCollection";
    features: GeoJsonFeature[];
  };
}

export interface RetrievedEvidence {
  query: string;
  results: EvidenceObject[];
  limitations: string[];
}

export interface CoverageScore {
  coverage_score: number;
  available: number;
  partial: number;
  missing: number;
  unknown: number;
  not_applicable: number;
}

export interface ReadinessMatrixItem {
  category_id: string;
  label: string;
  status: ReadinessStatus;
  summary: string;
  evidence_refs: string[];
  recommended_next_action: string;
}

export interface Finding {
  finding_id: string;
  title: string;
  summary: string;
  evidence_refs: string[];
  source_document: string | null;
  page: number | null;
  chunk_id: string | null;
}

export interface MissingInformationItem {
  item_id: string;
  category_id: string;
  description: string;
  evidence_refs: string[];
  recommended_next_action: string;
}

export interface RiskSignal {
  signal_id: string;
  title: string;
  description: string;
  evidence_refs: string[];
  priority: Priority;
}

export interface ChecklistItem {
  item_id: string;
  task: string;
  reason: string;
  evidence_refs: string[];
  priority: Priority;
}

export interface Dossier {
  dossier_id: string;
  site_context: SiteContext;
  generated_at: string;
  building_summary: string;
  public_context: string;
  planning_findings: Finding[];
  readiness_matrix: ReadinessMatrixItem[];
  coverage_score: CoverageScore;
  missing_information_checklist: MissingInformationItem[];
  technical_risk_signals: RiskSignal[];
  inspection_checklist: ChecklistItem[];
  evidence: EvidenceObject[];
  limitations: string[];
}
