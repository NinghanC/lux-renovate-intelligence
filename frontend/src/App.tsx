import { AlertTriangle, Loader2, MapPinPlus, Maximize2, Play, SlidersHorizontal, Trash2, X, UploadCloud } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import {
  generateDossier,
  getDocumentSourceBlobUrl,
  getActiveDocuments,
  removeActiveDocument,
  updateActiveDocumentType,
  getSiteContext,
  getSiteGeoJson,
  getSites,
  uploadDocuments
} from "./api/client";
import type { DemoSite, Dossier, EvidenceObject, GeoJsonFeature, SiteContext, SiteGeoJsonResponse, SourceRecordPublic } from "./types/dossier";

type ViewKey = "matrix" | "documents" | "followup" | "system";
type MissionTypeKey =
  | "technical_control"
  | "hvac_comfort_audit"
  | "environmental_classified_review"
  | "asbestos_pollutant_control"
  | "commissioning_maintenance"
  | "survey_scan_preparation"
  | "expertise_claim_review";

type DrawnMapPoint = {
  id: string;
  lat: number;
  lon: number;
  distance_m: number;
};

type FollowUpState = {
  requestStatus: string;
  notes: string;
  includeInEmail: boolean;
};

type FollowUpRow = {
  key: string;
  title: string;
  relatedItem: string;
  criticality: string;
  suggestion: string;
  evidenceRefs: string[];
};

const views: Array<{ key: ViewKey; label: string }> = [
  { key: "matrix", label: "Mission Readiness" },
  { key: "documents", label: "Case Documents" },
  { key: "followup", label: "Follow-up" },
  { key: "system", label: "System Transparency" }
];

const missionTypeOptions: Array<{ value: MissionTypeKey; label: string; prompt: string }> = [
  {
    value: "technical_control",
    label: "Technical control",
    prompt: "Prepare a technical control mission dossier with focus on regulatory context, drawings, structural unknowns, fire safety documents, and site inspection priorities."
  },
  {
    value: "hvac_comfort_audit",
    label: "HVAC / comfort audit",
    prompt: "Prepare an HVAC and comfort audit mission dossier with focus on MEP records, energy performance, water infiltration, comfort risks, and measurements to plan."
  },
  {
    value: "environmental_classified_review",
    label: "Environmental / classified establishment review",
    prompt: "Prepare an environmental or classified establishment review dossier with focus on authorization evidence, pollutant documentation, technical installations, and expert validation needs."
  },
  {
    value: "asbestos_pollutant_control",
    label: "Asbestos / pollutant control",
    prompt: "Prepare an asbestos and pollutant control mission dossier with focus on hazardous material documentation, missing surveys, sampling needs, and limits on conclusions."
  },
  {
    value: "commissioning_maintenance",
    label: "Commissioning / maintenance",
    prompt: "Prepare a commissioning and maintenance mission dossier with focus on maintenance records, MEP evidence, incomplete commissioning information, and controls to perform."
  },
  {
    value: "survey_scan_preparation",
    label: "Survey / 3D scan preparation",
    prompt: "Prepare a survey and 3D scan mission dossier with focus on site identity, existing drawings, scan planning, geometry unknowns, and field measurements."
  },
  {
    value: "expertise_claim_review",
    label: "Expertise / defect / claim review",
    prompt: "Prepare an expertise, defect, or claim review dossier with focus on observed conditions, missing evidence, water ingress, envelope defects, and expert validation tasks."
  }
];

const phaseOrder = [
  "Case identification",
  "Required documents",
  "Technical assessment",
  "Site inspection preparation",
  "Risk and compliance",
  "Client follow-up"
];

const statusLabels: Record<string, string> = {
  available: "Found",
  partial: "Partial",
  missing: "Missing",
  unknown: "Unknown",
  not_applicable: "Not applicable"
};

const priorityLabels: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low"
};

const uploadSubtypeOptions = [
  { value: "", label: "Auto classify" },
  { value: "condition_observation", label: "Condition observation" },
  { value: "inspection_report", label: "Inspection report" },
  { value: "drawing_or_plan", label: "Drawing or plan" },
  { value: "maintenance_record", label: "Maintenance record" },
  { value: "energy_certificate_or_audit", label: "Energy certificate or audit" },
  { value: "fire_safety_dossier", label: "Fire safety dossier" },
  { value: "hazardous_material_survey", label: "Hazardous material survey" },
  { value: "environmental_authorization", label: "Environmental authorization" },
  { value: "classified_establishment_document", label: "Classified establishment document" },
  { value: "asbestos_pollutant_document", label: "Asbestos or pollutant document" },
  { value: "commissioning_report", label: "Commissioning report" },
  { value: "hvac_mep_document", label: "HVAC or MEP document" },
  { value: "comfort_energy_document", label: "Comfort or energy document" },
  { value: "survey_scan_document", label: "Survey or 3D scan document" },
  { value: "expertise_claim_document", label: "Expertise, claim, or defect document" },
  { value: "owner_note", label: "Owner note" },
  { value: "photo_or_image_note", label: "Photo or scan note" }
];

const activeDocumentTypeOptions = [
  ...uploadSubtypeOptions.filter((option) => option.value),
  { value: "unknown_upload", label: "Other or unknown" }
];

const buildingTypeLabels: Record<string, string> = {
  residential: "Residential",
  mixed_use: "Mixed use",
  unknown: "Unknown"
};

function labelize(value: string) {
  return value.replace(/_/g, " ");
}

function buildingTypeLabel(value: string | null) {
  return buildingTypeLabels[value ?? "unknown"] ?? labelize(value ?? "unknown");
}

function statusLabel(value: string) {
  return statusLabels[value] ?? labelize(value);
}

function priorityLabel(value: string) {
  return priorityLabels[value] ?? value;
}

function criticalityLabel(value?: string | null) {
  if (value === "critical") return "Critical";
  if (value === "important") return "Important";
  if (value === "optional") return "Optional";
  return "Important";
}

function missionTypeLabel(value: MissionTypeKey) {
  return missionTypeOptions.find((option) => option.value === value)?.label ?? labelize(value);
}

function generationModeLabel(value?: string | null) {
  if (!value) return "Unknown";
  if (value === "mock") return "Demo";
  if (value === "real_llm") return "Real LLM";
  return labelize(value);
}

function evidenceTypeLabel(type: string) {
  if (type === "derived_missing_information") return "Missing mission information";
  if (type === "site_profile") return "Site profile";
  if (type === "planning_document") return "Planning document";
  if (type === "uploaded_document") return "Uploaded document";
  if (type === "geospatial") return "Geospatial context";
  return labelize(type);
}

function withPageHash(url: string, page?: number | null) {
  if (!page) return url;
  try {
    const parsed = new URL(url);
    parsed.hash = `page=${page}`;
    return parsed.toString();
  } catch {
    return `${url}#page=${page}`;
  }
}

function evidenceSourceHref(evidence: EvidenceObject | undefined) {
  if (!evidence) return null;
  if (evidence.source_url) return withPageHash(evidence.source_url, evidence.page);
  return null;
}

function evidenceRefParts(evidence: EvidenceObject | undefined, fallback: string) {
  if (!evidence) return { fileName: fallback, locator: null };
  return { fileName: evidenceFileName(evidence), locator: evidenceLocatorLabel(evidence) };
}

function evidenceFileName(evidence: EvidenceObject) {
  const rawName = evidence.source_name.split(/[\\/]/).pop() ?? evidence.source_name;
  const uploadedMatch = rawName.match(/^.+?_upload_[a-f0-9]{12}_(.+)$/i);
  return uploadedMatch?.[1] ?? rawName;
}

function sourceRecordFileName(source: SourceRecordPublic) {
  const original = source.metadata.original_filename;
  if (typeof original === "string" && original.trim()) return original;
  const rawName = source.display_name.split(/[\\/]/).pop() ?? source.display_name;
  const uploadedMatch = rawName.match(/^.+?_upload_[a-f0-9]{12}_(.+)$/i);
  return uploadedMatch?.[1] ?? rawName;
}

function evidenceLocatorLabel(evidence: EvidenceObject) {
  const page = evidence.page ?? evidence.locator?.page;
  const lineStart = evidence.locator?.line_start ?? metadataNumber(evidence.metadata.line_start);
  const lineEnd = evidence.locator?.line_end ?? metadataNumber(evidence.metadata.line_end);
  if (!page && !lineStart) return null;
  const pageLabel = page ? `p.${page}` : null;
  const lineLabel = lineStart ? `lines ${lineEnd && lineEnd !== lineStart ? `${lineStart}-${lineEnd}` : lineStart}` : null;
  return [pageLabel, lineLabel].filter(Boolean).join(" ");
}

function metadataNumber(value: unknown) {
  if (typeof value === "number") return value;
  if (typeof value === "string" && /^\d+$/.test(value)) return Number(value);
  return null;
}

function sourceTypeLabel(type: string) {
  const labels: Record<string, string> = {
    official_planning_pdf: "Official planning",
    uploaded_document: "Uploaded documents",
    uploaded_image: "Uploaded images",
    site_profile: "Site profile",
    geojson: "Geo context",
    derived: "Derived missing information"
  };
  return labels[type] ?? evidenceTypeLabel(type);
}

function sourceTypeCoverage(evidence: EvidenceObject[]) {
  const counts = new Map<string, number>();
  for (const item of evidence) {
    const key = item.source_type ?? item.evidence_type;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((left, right) => right.count - left.count || sourceTypeLabel(left.type).localeCompare(sourceTypeLabel(right.type)));
}

function scoredCoverageCategories(dossier: Dossier) {
  const coverage = dossier.coverage_score;
  return coverage.available + coverage.partial + coverage.missing + coverage.unknown;
}

function criticalMissingItems(dossier: Dossier) {
  return dossier.readiness_matrix.filter((item) => item.status === "missing" && (item.criticality ?? "important") === "critical");
}

function preparationStatus(dossier: Dossier) {
  const score = dossier.coverage_score.coverage_score;
  const criticalMissing = criticalMissingItems(dossier).length;
  if (score >= 85 && criticalMissing === 0) return "High";
  if (score >= 50 && criticalMissing < 3) return "Partial";
  return "Insufficient";
}

function readinessItemsByPhase(dossier: Dossier) {
  const grouped = new Map<string, Dossier["readiness_matrix"]>();
  for (const item of dossier.readiness_matrix) {
    const phase = item.phase || "Client follow-up";
    grouped.set(phase, [...(grouped.get(phase) ?? []), item]);
  }
  return Array.from(grouped.entries())
    .sort(([left], [right]) => phaseIndex(left) - phaseIndex(right) || left.localeCompare(right))
    .map(([title, items]) => ({ title, items }));
}

function missionReadinessPhaseGroups(dossier: Dossier) {
  return readinessItemsByPhase(dossier)
    .filter((group) => !["Case identification", "Required documents"].includes(group.title));
}

function phaseIndex(phase: string) {
  const index = phaseOrder.indexOf(phase);
  return index === -1 ? phaseOrder.length : index;
}

function formatDistance(distance?: number) {
  if (distance === undefined) return null;
  if (distance < 1000) return `${Math.round(distance)} m`;
  return `${(distance / 1000).toFixed(1)} km`;
}

function distanceMeters(left: CoordinatesLike, right: CoordinatesLike) {
  const radius = 6371008.8;
  const lat1 = (left.lat * Math.PI) / 180;
  const lat2 = (right.lat * Math.PI) / 180;
  const deltaLat = ((right.lat - left.lat) * Math.PI) / 180;
  const deltaLon = ((right.lon - left.lon) * Math.PI) / 180;
  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
  return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

type CoordinatesLike = {
  lat: number;
  lon: number;
};

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function App() {
  const [sites, setSites] = useState<DemoSite[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [siteContext, setSiteContext] = useState<SiteContext | null>(null);
  const [siteGeoJson, setSiteGeoJson] = useState<SiteGeoJsonResponse | null>(null);
  const [activeDocuments, setActiveDocuments] = useState<SourceRecordPublic[]>([]);
  const [drawnMapPointsBySite, setDrawnMapPointsBySite] = useState<Record<string, DrawnMapPoint[]>>({});
  const [mapDrawingEnabled, setMapDrawingEnabled] = useState(false);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [activeView, setActiveView] = useState<ViewKey>("matrix");
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null);
  const [mapFullscreen, setMapFullscreen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadPanelOpen, setUploadPanelOpen] = useState(false);
  const [uploadSubtype, setUploadSubtype] = useState("");
  const [siteListLoading, setSiteListLoading] = useState(true);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [missionType, setMissionType] = useState<MissionTypeKey>("technical_control");
  const [investigationQuestion, setInvestigationQuestion] = useState("");
  const [includeUploadedDocuments, setIncludeUploadedDocuments] = useState(true);
  const [maxEvidence, setMaxEvidence] = useState(12);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSite = useMemo(
    () => sites.find((site) => site.site_id === selectedSiteId) ?? null,
    [selectedSiteId, sites]
  );
  const evidenceById = useMemo(
    () => new Map((dossier?.evidence ?? []).map((item) => [item.evidence_id, item])),
    [dossier]
  );
  const drawnMapPoints = drawnMapPointsBySite[selectedSiteId] ?? [];

  useEffect(() => {
    setSiteListLoading(true);
    void getSites()
      .then((payload) => {
        setSites(payload);
        setSelectedSiteId(payload[0]?.site_id ?? "");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setSiteListLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedSiteId) return;
    setDossier(null);
    setSiteGeoJson(null);
    setActiveDocuments([]);
    setMapDrawingEnabled(false);
    setActiveView("matrix");
    setHighlightedEvidenceId(null);
    setError(null);
    void Promise.all([getSiteContext(selectedSiteId), getSiteGeoJson(selectedSiteId), getActiveDocuments(selectedSiteId)])
      .then(([context, geojson, documents]) => {
        setSiteContext(context);
        setSiteGeoJson(geojson);
        setActiveDocuments(documents);
      })
      .catch((err: Error) => setError(err.message));
  }, [selectedSiteId]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length || !selectedSiteId) return;
    setUploading(true);
    setError(null);
    setUploadSuccess(null);
    try {
      await uploadDocuments(selectedSiteId, files, uploadSubtype || undefined, false);
      setActiveDocuments(await getActiveDocuments(selectedSiteId));
      setUploadSuccess(`${files.length} document${files.length === 1 ? "" : "s"} uploaded. ${files.length === 1 ? "It" : "They"} will be included the next time you generate.`);
      setUploadPanelOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleRemoveActiveDocument(sourceId: string) {
    if (!selectedSiteId) return;
    setError(null);
    try {
      setActiveDocuments(await removeActiveDocument(selectedSiteId, sourceId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove active document");
    }
  }

  async function handleUpdateActiveDocumentType(sourceId: string, sourceSubtype: string) {
    if (!selectedSiteId) return;
    setError(null);
    try {
      setActiveDocuments(await updateActiveDocumentType(selectedSiteId, sourceId, sourceSubtype));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update active document type");
    }
  }

  async function handleGenerate() {
    if (!selectedSiteId) return;
    setLoading(true);
    setError(null);
    const missionPrompt = missionTypeOptions.find((option) => option.value === missionType)?.prompt;
    const generationQuestion = [missionPrompt, investigationQuestion.trim()].filter(Boolean).join("\n\n");
    try {
      const generated = await generateDossier(selectedSiteId, {
        query: generationQuestion,
        includeUploadedDocuments,
        maxEvidence,
        forceRefresh
      });
      setDossier(generated);
      setActiveView("matrix");
      setHighlightedEvidenceId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dossier generation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleEvidenceRefClick(evidenceId: string) {
    const evidence = evidenceById.get(evidenceId);
    const href = evidenceSourceHref(evidence);
    setHighlightedEvidenceId(evidenceId);
    window.setTimeout(() => {
      document.getElementById(`evidence-${evidenceId}`)?.scrollIntoView({
        behavior: prefersReducedMotion() ? "auto" : "smooth",
        block: "center"
      });
    }, 0);
    if (evidence?.source_id && ["official_planning_pdf", "uploaded_document", "uploaded_image"].includes(evidence.source_type ?? "")) {
      const opened = window.open("about:blank", "_blank", "noopener,noreferrer");
      try {
        const blobUrl = await getDocumentSourceBlobUrl(evidence.source_id);
        const documentUrl = withPageHash(blobUrl, evidence.page);
        if (opened) {
          opened.location.href = documentUrl;
        } else {
          window.open(documentUrl, "_blank", "noopener,noreferrer");
        }
        window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
      } catch (err) {
        if (opened) opened.close();
        setError(err instanceof Error ? err.message : "Could not open source document");
      }
    } else if (href) {
      window.open(href, "_blank", "noopener,noreferrer");
    }
  }

  function handleAddDrawnMapPoint(lat: number, lon: number) {
    if (!siteContext || !selectedSiteId) return;
    const point: DrawnMapPoint = {
      id: `drawn_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
      lat,
      lon,
      distance_m: distanceMeters(siteContext.coordinates, { lat, lon })
    };
    setDrawnMapPointsBySite((current) => ({
      ...current,
      [selectedSiteId]: [...(current[selectedSiteId] ?? []), point]
    }));
  }

  function handleClearDrawnMapPoints() {
    if (!selectedSiteId) return;
    setDrawnMapPointsBySite((current) => ({ ...current, [selectedSiteId]: [] }));
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">BM</div>
          <div>
            <h1>Building Mission Readiness</h1>
            <p>Evidence-backed mission preparation</p>
          </div>
        </div>

        <div className="control-group">
          <label htmlFor="site">Demo mission case</label>
          <select id="site" value={selectedSiteId} onChange={(event) => setSelectedSiteId(event.target.value)}>
            {siteListLoading ? <option value="">Loading cases...</option> : null}
            {sites.map((site) => (
              <option key={site.site_id} value={site.site_id}>
                {site.display_name}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="mission-type">Mission type</label>
          <select
            id="mission-type"
            value={missionType}
            onChange={(event) => setMissionType(event.target.value as MissionTypeKey)}
          >
            {missionTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {selectedSite ? (
          <div className="site-card">
            <strong>{selectedSite.commune}</strong>
            <span>{selectedSite.description}</span>
          </div>
        ) : null}

        <div className="advanced-options">
          <button
            className={`advanced-toggle ${advancedOpen ? "active" : ""}`}
            type="button"
            onClick={() => setAdvancedOpen((open) => !open)}
            aria-expanded={advancedOpen}
            aria-controls="advanced-fields"
          >
            <SlidersHorizontal size={16} />
            Advanced options
          </button>
          {advancedOpen ? (
            <div className="advanced-fields" id="advanced-fields">
              <label className="field">
                <span>Additional investigation question</span>
                <textarea
                  rows={3}
                  value={investigationQuestion}
                  onChange={(event) => setInvestigationQuestion(event.target.value)}
                  placeholder="Add a specific focus, missing document, building system, defect, or authorization question..."
                />
              </label>
              <label className="field">
                <span>Max evidence</span>
                <select
                  value={maxEvidence}
                  onChange={(event) => setMaxEvidence(Number(event.target.value))}
                >
                  <option value={8}>8</option>
                  <option value={12}>12</option>
                  <option value={20}>20</option>
                </select>
              </label>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={includeUploadedDocuments}
                  onChange={(event) => setIncludeUploadedDocuments(event.target.checked)}
                />
                <span>Include case documents</span>
              </label>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={forceRefresh}
                  onChange={(event) => setForceRefresh(event.target.checked)}
                />
                <span>Force refresh</span>
              </label>
            </div>
          ) : null}
        </div>

        <div className="actions">
          <button
            className="icon-button"
            type="button"
            title="Upload case document"
            aria-label={uploadPanelOpen ? "Close document upload panel" : "Open document upload panel"}
            aria-expanded={uploadPanelOpen}
            onClick={() => setUploadPanelOpen((open) => !open)}
            disabled={!selectedSiteId || uploading}
          >
            <UploadCloud size={18} />
          </button>
          <button className="primary-button" type="button" onClick={handleGenerate} disabled={!selectedSiteId || loading}>
            {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            {loading ? "Generating" : "Generate dossier"}
          </button>
        </div>

        {uploadPanelOpen ? (
          <div className="upload-panel">
            <label htmlFor="upload-subtype">Case document type</label>
            <select
              id="upload-subtype"
              value={uploadSubtype}
              onChange={(event) => setUploadSubtype(event.target.value)}
            >
              {uploadSubtypeOptions.map((option) => (
                <option key={option.value || "auto"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <label className="file-select-button">
              {uploading ? <Loader2 className="spin" size={16} /> : <UploadCloud size={16} />}
              {uploading ? "Uploading" : "Choose file"}
              <input type="file" accept=".pdf,.txt,.md,.markdown" onChange={handleUpload} disabled={uploading} multiple />
            </label>
          </div>
        ) : null}

        {uploading ? <p className="quiet">Uploading case document...</p> : null}
        {uploadSuccess ? <p className="quiet success-text">{uploadSuccess}</p> : null}
      </aside>

      <section className="workspace">
        {error ? (
          <div className="banner">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

          <SiteContextBlock
            siteContext={siteContext}
            siteGeoJson={siteGeoJson}
            drawnMapPoints={drawnMapPoints}
            drawingEnabled={mapDrawingEnabled}
            onToggleDrawing={() => setMapDrawingEnabled((enabled) => !enabled)}
            onAddDrawnPoint={handleAddDrawnMapPoint}
            onClearDrawnPoints={handleClearDrawnMapPoints}
            onOpenMap={() => setMapFullscreen(true)}
          />

          <ActiveDocumentsPanel
            documents={activeDocuments}
            onRemove={handleRemoveActiveDocument}
            onTypeChange={handleUpdateActiveDocumentType}
          />

        {dossier ? (
          <>
            <CaseHeader
              selectedSite={selectedSite}
              siteContext={siteContext}
              missionType={missionType}
            />
            <section className="dossier-hero">
              <MissionPreparationSummary dossier={dossier} />
              <KpiCards dossier={dossier} />
            </section>

            <nav className="tabs" aria-label="Dossier views">
              {views.map((view) => (
                <button
                  key={view.key}
                  className={activeView === view.key ? "active" : ""}
                  type="button"
                  aria-current={activeView === view.key ? "page" : undefined}
                  onClick={() => setActiveView(view.key)}
                >
                  {view.label}
                </button>
              ))}
            </nav>

            <section className="view-panel">
              {renderView(activeView, dossier, evidenceById, handleEvidenceRefClick, missionType)}
            </section>
          </>
        ) : (
          <CaseSetupIntro missionType={missionType} selectedSite={selectedSite} />
        )}
      </section>
      {mapFullscreen && siteContext ? (
        <MapDialog
          siteContext={siteContext}
          siteGeoJson={siteGeoJson}
          drawnMapPoints={drawnMapPoints}
          drawingEnabled={mapDrawingEnabled}
          onToggleDrawing={() => setMapDrawingEnabled((enabled) => !enabled)}
          onAddDrawnPoint={handleAddDrawnMapPoint}
          onClearDrawnPoints={handleClearDrawnMapPoints}
          onClose={() => setMapFullscreen(false)}
        />
      ) : null}
    </main>
  );
}

function CaseSetupIntro({
  missionType,
  selectedSite
}: {
  missionType: MissionTypeKey;
  selectedSite: DemoSite | null;
}) {
  return (
    <section className="empty-state case-intro">
      <div>
        <span className="eyebrow">Case setup</span>
        <h2>Prepare a building mission readiness dossier</h2>
        <p>
          Select the case, choose the mission type, add local case documents if available, then generate a dossier that separates
          evidence present, missing mission-critical information, and expert validation tasks.
        </p>
      </div>
      <div className="case-intro-grid">
        <div>
          <strong>Current case</strong>
          <span>{selectedSite?.display_name ?? "No case selected"}</span>
        </div>
        <div>
          <strong>Mission focus</strong>
          <span>{missionTypeLabel(missionType)}</span>
        </div>
        <div>
          <strong>Expected outputs</strong>
          <span>Document inventory, evidence review, readiness matrix, mission checklist</span>
        </div>
      </div>
    </section>
  );
}

function CaseHeader({
  selectedSite,
  siteContext,
  missionType
}: {
  selectedSite: DemoSite | null;
  siteContext: SiteContext | null;
  missionType: MissionTypeKey;
}) {
  return (
    <section className="case-header">
      <div className="case-header-main">
        <span className="eyebrow">Mission case</span>
        <h2>{selectedSite?.display_name ?? siteContext?.address ?? "Selected building case"}</h2>
        <p>{siteContext?.address ?? selectedSite?.description ?? "Case context loaded from local demo data."}</p>
      </div>
      <dl className="case-header-facts">
        <div>
          <dt>Commune</dt>
          <dd>{siteContext?.commune ?? selectedSite?.commune ?? "Unknown"}</dd>
        </div>
        <div>
          <dt>Mission type</dt>
          <dd>{missionTypeLabel(missionType)}</dd>
        </div>
      </dl>
    </section>
  );
}

function ActiveDocumentsPanel({
  documents,
  onRemove,
  onTypeChange
}: {
  documents: SourceRecordPublic[];
  onRemove: (sourceId: string) => void;
  onTypeChange: (sourceId: string, sourceSubtype: string) => void;
}) {
  const uploaded = documents.filter((document) => document.source_type === "uploaded_document" || document.source_type === "uploaded_image");
  return (
    <section className="panel active-documents-panel">
      <div className="view-heading">
        <span className="eyebrow">Active case documents</span>
        <h2>Documents queued for the next generation</h2>
        <p>New uploads are added to this queue. Remove any document you do not want included before generating.</p>
      </div>
      {uploaded.length ? (
        <div className="active-document-list">
          {uploaded.map((document) => (
            <div className="active-document-row" key={document.source_id}>
              <div className="active-document-copy">
                <strong>{sourceRecordFileName(document)}</strong>
                <small>{document.status === "available" ? "Uploaded locally" : labelize(document.status)}</small>
              </div>
              <label className="active-document-type">
                <span>Case document type</span>
                <select
                  value={document.source_subtype ?? "unknown_upload"}
                  onChange={(event) => onTypeChange(document.source_id, event.target.value)}
                >
                  {activeDocumentTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="icon-button remove-document-button"
                type="button"
                title="Remove from next generation"
                aria-label={`Remove ${sourceRecordFileName(document)} from next generation`}
                onClick={() => onRemove(document.source_id)}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">No active uploaded documents for this case yet.</p>
      )}
    </section>
  );
}

function SiteContextBlock({
  siteContext,
  siteGeoJson,
  drawnMapPoints,
  drawingEnabled,
  onToggleDrawing,
  onAddDrawnPoint,
  onClearDrawnPoints,
  onOpenMap
}: {
  siteContext: SiteContext | null;
  siteGeoJson: SiteGeoJsonResponse | null;
  drawnMapPoints: DrawnMapPoint[];
  drawingEnabled: boolean;
  onToggleDrawing: () => void;
  onAddDrawnPoint: (lat: number, lon: number) => void;
  onClearDrawnPoints: () => void;
  onOpenMap: () => void;
}) {
  if (!siteContext) {
    return (
      <section className="panel site-context-panel">
        <h2>Case setup</h2>
        <p className="empty">Select a demo site.</p>
      </section>
    );
  }

  return (
    <section className="panel site-context-panel">
      <h2>Case setup</h2>
      <div className="site-context-layout">
        <dl className="facts">
          <dt>Address</dt>
          <dd>{siteContext.address}</dd>
          <dt>Commune</dt>
          <dd>{siteContext.commune}</dd>
          <dt>Coordinates</dt>
          <dd>
            {siteContext.coordinates.lat.toFixed(4)}, {siteContext.coordinates.lon.toFixed(4)}
          </dd>
          <dt>Building type</dt>
          <dd>{buildingTypeLabel(siteContext.building_type)}</dd>
          <dt>Approx. year</dt>
          <dd>{siteContext.approx_year_built ?? "Unknown"}</dd>
          <dt>Footprint</dt>
          <dd>{siteContext.data_quality.footprint_available ? "Available" : "Not verified"}</dd>
          <dt>Nearby</dt>
          <dd>{siteContext.nearby_features.length ? siteContext.nearby_features.join(", ") : "Unknown"}</dd>
        </dl>
        <div className="site-map-stack">
          <SiteMap
            siteContext={siteContext}
            siteGeoJson={siteGeoJson}
            drawnMapPoints={drawnMapPoints}
            drawingEnabled={drawingEnabled}
            onToggleDrawing={onToggleDrawing}
            onAddDrawnPoint={onAddDrawnPoint}
            onClearDrawnPoints={onClearDrawnPoints}
            onOpenMap={onOpenMap}
          />
          <GeoJsonSummary siteGeoJson={siteGeoJson} />
        </div>
      </div>
    </section>
  );
}

function SiteMap({
  siteContext,
  siteGeoJson,
  drawnMapPoints,
  drawingEnabled,
  onToggleDrawing,
  onAddDrawnPoint,
  onClearDrawnPoints,
  onOpenMap,
  fullscreen = false
}: {
  siteContext: SiteContext;
  siteGeoJson?: SiteGeoJsonResponse | null;
  drawnMapPoints?: DrawnMapPoint[];
  drawingEnabled: boolean;
  onToggleDrawing: () => void;
  onAddDrawnPoint: (lat: number, lon: number) => void;
  onClearDrawnPoints: () => void;
  onOpenMap?: () => void;
  fullscreen?: boolean;
}) {
  const position: [number, number] = [siteContext.coordinates.lat, siteContext.coordinates.lon];
  const geoFeatures = siteGeoJson?.geojson.features ?? [];
  const drawnPoints = drawnMapPoints ?? [];

  return (
    <div className={`site-map${fullscreen ? " fullscreen-map" : ""}${drawingEnabled ? " drawing-enabled" : ""}`}>
      <div className="map-toolbar">
        {onOpenMap ? (
          <button className="map-expand-button" type="button" onClick={onOpenMap} title="Open full-screen map" aria-label="Open full-screen map">
            <Maximize2 size={16} />
          </button>
        ) : null}
        <button
          className={`map-tool-button ${drawingEnabled ? "active" : ""}`}
          type="button"
          onClick={onToggleDrawing}
          title="Add map point"
          aria-label={drawingEnabled ? "Stop adding map points" : "Add map point"}
          aria-pressed={drawingEnabled}
        >
          <MapPinPlus size={16} />
        </button>
        {drawnPoints.length ? (
          <button className="map-tool-button" type="button" onClick={onClearDrawnPoints} title="Clear map points" aria-label="Clear map points">
            <Trash2 size={16} />
          </button>
        ) : null}
      </div>
      <MapContainer
        center={position}
        zoom={15}
        scrollWheelZoom={false}
        zoomControl
        className="map-container"
      >
        <MapRecenter center={position} />
        <MapClickHandler enabled={drawingEnabled} onAddPoint={onAddDrawnPoint} />
        <TileLayer
          attribution='Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <CircleMarker
          center={position}
          radius={8}
          pathOptions={{ color: "#0f766e", fillColor: "#0f766e", fillOpacity: 0.9, weight: 2 }}
        >
          <Popup>
            Demo site location
            <br />
            Coordinates are approximate
          </Popup>
        </CircleMarker>
        {geoFeatures
          .filter((feature) => feature.properties.feature_type !== "demo_site")
          .map((feature) => (
            <GeoJsonPoint key={feature.properties.feature_id ?? feature.properties.name} feature={feature} />
          ))}
        {drawnPoints.map((point) => (
          <DrawnPoint key={point.id} point={point} />
        ))}
      </MapContainer>
    </div>
  );
}

function MapClickHandler({
  enabled,
  onAddPoint
}: {
  enabled: boolean;
  onAddPoint: (lat: number, lon: number) => void;
}) {
  useMapEvents({
    click(event) {
      if (enabled) onAddPoint(event.latlng.lat, event.latlng.lng);
    }
  });
  return null;
}

function MapRecenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, map.getZoom(), { duration: prefersReducedMotion() ? 0 : 0.6 });
  }, [center, map]);
  return null;
}

function DrawnPoint({ point }: { point: DrawnMapPoint }) {
  return (
    <CircleMarker
      center={[point.lat, point.lon]}
      radius={7}
      pathOptions={{ color: "#2563eb", fillColor: "#3b82f6", fillOpacity: 0.9, weight: 2 }}
    >
      <Popup>
        Drawn point
        <br />
        {formatDistance(point.distance_m)} from demo coordinate
      </Popup>
    </CircleMarker>
  );
}

function GeoJsonPoint({ feature }: { feature: GeoJsonFeature }) {
  const [lon, lat] = feature.geometry.coordinates;
  const distance = formatDistance(feature.properties.distance_m);
  return (
    <CircleMarker
      center={[lat, lon]}
      radius={6}
      pathOptions={{ color: "#d97706", fillColor: "#f59e0b", fillOpacity: 0.85, weight: 2 }}
    >
      <Popup>
        {feature.properties.name ?? "GeoJSON feature"}
        {distance ? (
          <>
            <br />
            {distance} from demo coordinate
          </>
        ) : null}
      </Popup>
    </CircleMarker>
  );
}

function GeoJsonSummary({ siteGeoJson }: { siteGeoJson: SiteGeoJsonResponse | null }) {
  const features = (siteGeoJson?.geojson.features ?? []).filter((feature) => feature.properties.feature_type !== "demo_site");
  if (!features.length) return null;
  return (
    <div className="geojson-summary">
      {features.slice(0, 3).map((feature) => (
        <div key={feature.properties.feature_id ?? feature.properties.name}>
          <span>{feature.properties.name ?? "GeoJSON feature"}</span>
          <strong>{formatDistance(feature.properties.distance_m)}</strong>
        </div>
      ))}
    </div>
  );
}

function MapDialog({
  siteContext,
  siteGeoJson,
  drawnMapPoints,
  drawingEnabled,
  onToggleDrawing,
  onAddDrawnPoint,
  onClearDrawnPoints,
  onClose
}: {
  siteContext: SiteContext;
  siteGeoJson: SiteGeoJsonResponse | null;
  drawnMapPoints: DrawnMapPoint[];
  drawingEnabled: boolean;
  onToggleDrawing: () => void;
  onAddDrawnPoint: (lat: number, lon: number) => void;
  onClearDrawnPoints: () => void;
  onClose: () => void;
}) {
  return (
    <div className="map-dialog-backdrop" role="dialog" aria-modal="true" aria-label="Site map">
      <div className="map-dialog">
        <div className="map-dialog-header">
          <div>
            <h2>Mission case map</h2>
            <p>
              {siteContext.address} / {siteContext.coordinates.lat.toFixed(4)},{" "}
              {siteContext.coordinates.lon.toFixed(4)}
            </p>
          </div>
          <button className="map-close-button" type="button" onClick={onClose} title="Close map" aria-label="Close map">
            <X size={18} />
          </button>
        </div>
        <SiteMap
          siteContext={siteContext}
          siteGeoJson={siteGeoJson}
          drawnMapPoints={drawnMapPoints}
          drawingEnabled={drawingEnabled}
          onToggleDrawing={onToggleDrawing}
          onAddDrawnPoint={onAddDrawnPoint}
          onClearDrawnPoints={onClearDrawnPoints}
          fullscreen
        />
      </div>
    </div>
  );
}

function renderView(
  view: ViewKey,
  dossier: Dossier,
  evidenceById: Map<string, EvidenceObject>,
  onEvidenceRefClick: (evidenceId: string) => void,
  missionType: MissionTypeKey
) {
  if (view === "documents") {
    return <DocumentInventory evidence={dossier.evidence} />;
  }

  if (view === "matrix") {
    return <MissionReadiness dossier={dossier} evidenceById={evidenceById} onEvidenceRefClick={onEvidenceRefClick} />;
  }

  if (view === "followup") {
    return <FollowUpTab dossier={dossier} missionType={missionType} evidenceById={evidenceById} onEvidenceRefClick={onEvidenceRefClick} />;
  }

  return <SystemTransparency dossier={dossier} />;
}

function MissionReadiness({
  dossier,
  evidenceById,
  onEvidenceRefClick
}: {
  dossier: Dossier;
  evidenceById: Map<string, EvidenceObject>;
  onEvidenceRefClick: (evidenceId: string) => void;
}) {
  const grouped = missionReadinessPhaseGroups(dossier);
  return (
    <div className="readiness-view">
      <div className="view-heading">
        <span className="eyebrow">Mission readiness</span>
        <h2>Assessment topics for the mission</h2>
        <p>These accordions focus on technical assessment, site inspection preparation, and risk or compliance topics. Case identity and required-document tracking are handled in the case header, documents, and follow-up views.</p>
      </div>
      <div className="readiness-groups">
        {grouped.map((group, index) => (
          <ReadinessGroup
            key={group.title}
            title={group.title}
            items={group.items}
            evidenceById={evidenceById}
            onEvidenceRefClick={onEvidenceRefClick}
            defaultOpen={index === 0}
          />
        ))}
      </div>
    </div>
  );
}

function MissionPreparationSummary({ dossier }: { dossier: Dossier }) {
  const criticalMissing = criticalMissingItems(dossier).length;
  const followUps = followUpRows(dossier).length;
  const uploadedDocs = documentInventoryRows(dossier.evidence).filter((row) => row.sourceType === "uploaded_document" || row.sourceType === "uploaded_image");
  return (
    <div className="mission-summary">
      <span className="eyebrow">Mission preparation summary</span>
      <h2>{preparationStatus(dossier)} preparation status</h2>
      <p>{dossier.building_summary}</p>
      <p>
        The current case file includes {uploadedDocs.length} active uploaded document{uploadedDocs.length === 1 ? "" : "s"} and produces {followUps} follow-up action{followUps === 1 ? "" : "s"}. {criticalMissing ? `${criticalMissing} critical readiness item${criticalMissing === 1 ? "" : "s"} still need evidence or expert validation before the case can be treated as highly prepared.` : "No critical readiness item is currently missing from the validated matrix."}
      </p>
      <p className="summary-caveat">This is a mission-preparation view only. It is not a safety, structural, legal, environmental, authorization, or compliance certification.</p>
    </div>
  );
}

function KpiCards({ dossier }: { dossier: Dossier }) {
  const criticalMissing = criticalMissingItems(dossier).length;
  const uploadedDocs = documentInventoryRows(dossier.evidence).filter((row) => row.sourceType === "uploaded_document" || row.sourceType === "uploaded_image");
  const followUps = followUpRows(dossier).length;
  const checklistCount = dossier.inspection_checklist.length;
  const status = preparationStatus(dossier);
  return (
    <div className="kpi-board">
      <section className={`preparation-status-card ${status.toLowerCase()}`}>
        <span>Preparation status</span>
        <strong>{status}</strong>
        <p>{criticalMissing ? "Critical gap present. Resolve critical follow-up items before treating the case as highly prepared." : "No critical gap is currently flagged by the readiness matrix."}</p>
      </section>
      <div className="kpi-grid">
        <SummaryCard label="Critical missing" value={String(criticalMissing)} detail="Needs evidence or expert validation" />
        <SummaryCard label="Documents uploaded" value={String(uploadedDocs.length)} detail="Active local case documents" />
        <SummaryCard label="Documents processed" value={String(uploadedDocs.filter((row) => row.evidenceCount > 0).length)} detail="Evidence extracted" />
        <SummaryCard label="Follow-up actions" value={String(followUps)} detail="Requests and expert checks" />
        <SummaryCard label="Checklist items" value={String(checklistCount)} detail="Mission actions proposed" />
      </div>
    </div>
  );
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function ReadinessGroup({
  title,
  items,
  evidenceById,
  onEvidenceRefClick,
  defaultOpen = false
}: {
  title: string;
  items: Dossier["readiness_matrix"];
  evidenceById: Map<string, EvidenceObject>;
  onEvidenceRefClick: (evidenceId: string) => void;
  defaultOpen?: boolean;
}) {
  const missing = items.filter((item) => item.status === "missing").length;
  return (
    <details className="readiness-group" open={defaultOpen}>
      <summary className="readiness-group-header">
        <h2>{title}</h2>
        <span>{missing ? `${missing} missing` : "Evidence present"}</span>
      </summary>
      <div className="readiness-table-wrap">
        <table className="readiness-table">
          <thead>
            <tr>
              <th>Checklist item</th>
              <th>Criticality</th>
              <th>Status</th>
              <th>Evidence</th>
              <th>Business summary</th>
              <th>Action needed</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.category_id}>
                <td>{item.label}</td>
                <td>{criticalityLabel(item.criticality)}</td>
                <td><span className={`status ${item.status}`}>{statusLabel(item.status)}</span></td>
                <td><EvidenceRefs refs={item.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} compact /></td>
                <td>{item.summary}</td>
                <td>{item.recommended_next_action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function MissionChecklist({
  dossier,
  evidenceById,
  onEvidenceRefClick
}: {
  dossier: Dossier;
  evidenceById: Map<string, EvidenceObject>;
  onEvidenceRefClick: (evidenceId: string) => void;
}) {
  const grouped = checklistGroups(dossier);
  return (
    <div className="checklist-groups">
      {grouped.map((group) => (
        <List key={group.title} title={group.title}>
          {group.items.map((item) => (
            <article key={item.item_id} className="item">
              <span className={`priority ${item.priority}`}>Priority: {priorityLabel(item.priority)}</span>
              <h3>{item.task}</h3>
              <p>{item.reason}</p>
              <EvidenceRefs refs={item.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} />
            </article>
          ))}
        </List>
      ))}
    </div>
  );
}

function checklistGroups(dossier: Dossier) {
  const groups = new Map<string, Dossier["inspection_checklist"]>([
    ["Documents to request", []],
    ["Controls to perform", []],
    ["Measurements / scans to plan", []],
    ["Items requiring expert validation", []]
  ]);
  for (const item of dossier.inspection_checklist) {
    const group = checklistGroupTitle(item);
    groups.set(group, [...(groups.get(group) ?? []), item]);
  }
  return Array.from(groups.entries())
    .filter(([, items]) => items.length)
    .map(([title, items]) => ({ title, items }));
}

function checklistGroupTitle(item: Dossier["inspection_checklist"][number]) {
  const text = `${item.task} ${item.reason}`.toLowerCase();
  if (/(request|collect|obtain|document|certificate|record|drawing|inventory|authorization|dossier)/.test(text)) {
    return "Documents to request";
  }
  if (/(measure|scan|survey|sampling|sample|test|monitor|meter|laser|3d)/.test(text)) {
    return "Measurements / scans to plan";
  }
  if (/(expert|validate|engineer|specialist|laboratory|fire|structural|environmental|asbestos|pollutant)/.test(text)) {
    return "Items requiring expert validation";
  }
  return "Controls to perform";
}

function FollowUpTab({
  dossier,
  missionType,
  evidenceById,
  onEvidenceRefClick
}: {
  dossier: Dossier;
  missionType: MissionTypeKey;
  evidenceById: Map<string, EvidenceObject>;
  onEvidenceRefClick: (evidenceId: string) => void;
}) {
  const rows = followUpRows(dossier);
  const storageKey = `followup:${dossier.dossier_id}`;
  const [state, setState] = useState<Record<string, FollowUpState>>(() => readFollowUpState(storageKey));
  const [emailDraft, setEmailDraft] = useState("");

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(state));
  }, [state, storageKey]);

  function updateRow(key: string, patch: Partial<FollowUpState>) {
    setState((current) => ({
      ...current,
      [key]: { ...followUpStateFor(current, key), ...patch }
    }));
  }

  function generateEmailDraft() {
    const selectedRows = rows.filter((row) => followUpStateFor(state, row.key).includeInEmail);
    setEmailDraft(buildEmailDraft(dossier, missionType, selectedRows));
  }

  if (!rows.length) {
    return (
      <section className="empty-state inline-empty">
        <h2>Follow-up</h2>
        <p>No missing or partial follow-up items were generated for this dossier.</p>
      </section>
    );
  }

  return (
    <div className="followup-view">
      <div className="view-heading">
        <span className="eyebrow">Follow-up</span>
        <h2>Client requests and expert validation tasks</h2>
        <p>Track missing or partial information locally, then generate editable request wording for the client.</p>
      </div>
      <div className="followup-table-wrap">
        <table className="followup-table">
          <thead>
            <tr>
              <th>Follow-up item</th>
              <th>Related item</th>
              <th>Criticality</th>
              <th>Suggested request</th>
              <th>Status</th>
              <th>Notes</th>
              <th>Email</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rowState = followUpStateFor(state, row.key);
              return (
                <tr key={row.key}>
                  <td>{row.title}</td>
                  <td>{row.relatedItem}</td>
                  <td>{criticalityLabel(row.criticality)}</td>
                  <td>{row.suggestion}</td>
                  <td>
                    <select
                      value={rowState.requestStatus}
                      onChange={(event) => updateRow(row.key, { requestStatus: event.target.value })}
                      aria-label={`Request status for ${row.title}`}
                    >
                      {requestStatusOptions.map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <textarea
                      rows={2}
                      value={rowState.notes}
                      onChange={(event) => updateRow(row.key, { notes: event.target.value })}
                      placeholder="Internal note"
                      aria-label={`Internal note for ${row.title}`}
                    />
                  </td>
                  <td>
                    <label className="checkbox-field compact-check">
                      <input
                        type="checkbox"
                        checked={rowState.includeInEmail}
                        onChange={(event) => updateRow(row.key, { includeInEmail: event.target.checked })}
                      />
                      <span>Include</span>
                    </label>
                  </td>
                  <td><EvidenceRefs refs={row.evidenceRefs} evidenceById={evidenceById} onClick={onEvidenceRefClick} compact /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <section className="email-draft-panel">
        <div className="view-heading">
          <h2>Request email draft</h2>
          <p>This creates editable text only. The app does not send email.</p>
        </div>
        <button className="secondary-button" type="button" onClick={generateEmailDraft}>Generate email text</button>
        <textarea
          rows={10}
          value={emailDraft}
          onChange={(event) => setEmailDraft(event.target.value)}
          placeholder="Select follow-up rows, then generate editable request text."
          aria-label="Request email draft"
        />
      </section>
    </div>
  );
}

function followUpRows(dossier: Dossier): FollowUpRow[] {
  const matrixByCategory = new Map(dossier.readiness_matrix.map((item) => [item.category_id, item]));
  const rows: FollowUpRow[] = [];
  for (const item of dossier.missing_information_checklist) {
    const matrixItem = matrixByCategory.get(item.category_id);
    rows.push({
      key: `${dossier.dossier_id}:missing:${item.category_id}`,
      title: item.description,
      relatedItem: matrixItem?.label ?? labelize(item.category_id),
      criticality: matrixItem?.criticality ?? "important",
      suggestion: item.recommended_next_action,
      evidenceRefs: item.evidence_refs
    });
  }
  for (const signal of dossier.technical_risk_signals) {
    rows.push({
      key: `${dossier.dossier_id}:signal:${signal.signal_id}`,
      title: signal.title,
      relatedItem: "Expert validation",
      criticality: signal.priority === "high" ? "critical" : "important",
      suggestion: signal.description,
      evidenceRefs: signal.evidence_refs
    });
  }
  for (const item of dossier.readiness_matrix) {
    if (!["missing", "partial", "unknown"].includes(item.status)) continue;
    const key = `${dossier.dossier_id}:matrix:${item.category_id}`;
    if (rows.some((row) => row.key === key || row.relatedItem === item.label)) continue;
    rows.push({
      key,
      title: item.label,
      relatedItem: item.phase ?? "Mission readiness",
      criticality: item.criticality ?? "important",
      suggestion: item.recommended_next_action,
      evidenceRefs: item.evidence_refs
    });
  }
  return rows;
}

function readFollowUpState(storageKey: string): Record<string, FollowUpState> {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function followUpStateFor(state: Record<string, FollowUpState>, key: string): FollowUpState {
  return state[key] ?? { requestStatus: "Not requested", notes: "", includeInEmail: true };
}

function buildEmailDraft(dossier: Dossier, missionType: MissionTypeKey, rows: FollowUpRow[]) {
  const selected = rows.length ? rows : followUpRows(dossier);
  const items = selected.map((row) => `- ${row.suggestion}`).join("\n");
  return [
    `Subject: Missing documents for ${dossier.site_context.address}`,
    "",
    "Dear [Client/Contact],",
    "",
    `As part of the preparation for the ${missionTypeLabel(missionType)} mission regarding ${dossier.site_context.address}, we reviewed the documents currently available.`,
    "",
    "To continue the assessment, could you please provide the following missing information or documents:",
    "",
    items || "- [Add missing information request]",
    "",
    "If possible, please share the documents before [deadline].",
    "",
    "Thank you in advance.",
    "",
    "Best regards,"
  ].join("\n");
}

function GlossaryTab() {
  const terms = [
    ["High preparation coverage", "Most required case-file information is present and no critical readiness category is missing. This is not an approval or compliance status."],
    ["Partial preparation coverage", "Some useful evidence is available, but the case still needs missing documents, clarification, or expert checks before the mission is well prepared."],
    ["Insufficient preparation coverage", "The case file lacks enough evidence for reliable mission preparation, or one or more critical categories are missing."],
    ["Found", "The required information was identified in one or more case evidence sources."],
    ["Partial", "Some relevant information was found, but it is incomplete, indirect, or still needs expert validation."],
    ["Missing", "The required information was not found in the current case evidence."],
    ["Not applicable", "The category does not apply to the selected mission context and is excluded from the score."],
    ["Critical", "Information that can block high preparation coverage if missing."],
    ["Important", "Information that materially improves mission preparation but may not block every preliminary action."],
    ["Optional", "Helpful supporting information that does not normally block the mission preparation workflow."],
    ["Official public source", "Planning or public documents from official sources. These still need mission-specific interpretation."],
    ["User-provided source", "Documents uploaded locally by the user. Useful for preparation, but not independently verified by the app."],
    ["System-derived evidence", "A generated record that explains missing information for traceability. It is not an external document."],
    ["Readiness score", "A case-file evidence coverage indicator based on the validated readiness matrix."],
    ["Critical warning", "If critical information is missing, the mission cannot be shown as high preparation coverage even if the numeric score is otherwise strong."]
  ];
  return (
    <div className="glossary-view">
      <div className="view-heading">
        <span className="eyebrow">Glossary</span>
        <h2>Business rules and labels</h2>
        <p>The readiness score is not a safety, structural, legal, environmental, authorization, or compliance certification.</p>
      </div>
      <div className="glossary-grid">
        {terms.map(([term, definition]) => (
          <article className="item" key={term}>
            <h3>{term}</h3>
            <p>{definition}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

type DocumentInventoryRow = {
  key: string;
  sourceType: string;
  fileName: string;
  detectedType: string;
  status: string;
  evidenceCount: number;
  supports: string[];
  authority: string;
  used: boolean;
};

const requestStatusOptions = [
  "Not requested",
  "Requested",
  "Reminder needed",
  "Received but not uploaded",
  "Uploaded",
  "Not applicable"
];

function DocumentInventory({ evidence }: { evidence: EvidenceObject[] }) {
  const rows = documentInventoryRows(evidence);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  if (!rows.length) {
    return (
      <section className="empty-state inline-empty">
        <h2>Case document inventory</h2>
        <p>No case documents have been parsed into dossier evidence yet.</p>
      </section>
    );
  }
  return (
    <div className="inventory-view">
      <div className="view-heading">
        <span className="eyebrow">Case document inventory</span>
        <h2>Documents and sources available to prepare the mission</h2>
        <p>Each row is grouped by file or source so repeated evidence snippets do not look like repeated uploads.</p>
      </div>
      <div className="inventory-table-wrap">
        <table className="inventory-table">
          <thead>
            <tr>
              <th>File or source</th>
              <th>Detected type</th>
              <th>Selected type</th>
              <th>Status</th>
              <th>Evidence extracted</th>
              <th>Supports</th>
              <th>Trust label</th>
              <th>Latest dossier</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{row.fileName}</td>
                <td>{row.detectedType}</td>
                <td>
                  <select
                    value={overrides[row.key] ?? ""}
                    onChange={(event) => setOverrides((current) => ({ ...current, [row.key]: event.target.value }))}
                    title="Session override only"
                  >
                    {uploadSubtypeOptions.map((option) => (
                      <option key={option.value || "auto"} value={option.value}>
                        {option.value ? option.label : "Use detected type"}
                      </option>
                    ))}
                  </select>
                  {overrides[row.key] ? <small>Session override</small> : null}
                </td>
                <td>{row.status}</td>
                <td>{row.evidenceCount}</td>
                <td>{row.supports.length ? row.supports.slice(0, 3).map(labelize).join(", ") : "General context"}</td>
                <td>{row.authority}</td>
                <td>{row.used ? "Used" : "Not used"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function documentInventoryRows(evidence: EvidenceObject[]): DocumentInventoryRow[] {
  const grouped = new Map<string, EvidenceObject[]>();
  for (const item of evidence) {
    const key = documentInventoryGroupKey(item);
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }
  return Array.from(grouped.entries())
    .map(([key, items]) => {
      const first = items[0];
      const supports = Array.from(new Set(items.flatMap((item) => item.supports)));
      const detectedTypes = Array.from(
        new Set(items.map((item) => item.source_subtype).filter((value): value is string => Boolean(value)))
      );
      return {
        key,
        sourceType: first.source_type ?? first.evidence_type,
        fileName: evidenceFileName(first),
        detectedType: detectedTypeLabel(detectedTypes, first),
        status: documentStatusLabel(first, items.length),
        evidenceCount: items.length,
        supports,
        authority: authorityLabel(first),
        used: items.some((item) => item.evidence_id.startsWith("ev_"))
      };
    })
    .sort((left, right) => left.fileName.localeCompare(right.fileName));
}

function documentStatusLabel(evidence: EvidenceObject, evidenceCount: number) {
  if (evidence.source_type === "derived") return "System-derived";
  if (evidenceCount > 0) return "Evidence extracted";
  return "Processed";
}

function documentInventoryGroupKey(evidence: EvidenceObject) {
  const sourceType = evidence.source_type ?? evidence.evidence_type;
  if (sourceType === "uploaded_document" || sourceType === "uploaded_image") {
    return `${sourceType}:${evidenceFileName(evidence)}`;
  }
  if (sourceType === "derived") {
    return "derived:missing_information";
  }
  return evidence.source_id ?? `${sourceType}:${evidence.source_name}`;
}

function detectedTypeLabel(detectedTypes: string[], fallback: EvidenceObject) {
  if (detectedTypes.length === 1) return labelize(detectedTypes[0]);
  if (detectedTypes.length > 1) return `Multiple: ${detectedTypes.slice(0, 3).map(labelize).join(", ")}`;
  return sourceTypeLabel(fallback.source_type ?? fallback.evidence_type);
}

function authorityLabel(evidence: EvidenceObject) {
  if (evidence.source_type === "official_planning_pdf") return "Official public";
  if (evidence.source_type === "uploaded_document" || evidence.source_type === "uploaded_image") return "User-provided";
  if (evidence.source_type === "site_profile") return "Demo metadata";
  if (evidence.source_type === "geojson") return "Spatial context";
  if (evidence.source_type === "derived") return "System-derived";
  return evidence.authority_level ? labelize(evidence.authority_level) : "Unverified";
}

function SystemTransparency({ dossier }: { dossier: Dossier }) {
  const usage = dossier.usage;
  const review = dossier.semantic_review;
  const reviewUsage = dossier.semantic_review_usage;
  const tokenTotal = usage ? usage.total_tokens_reported ?? usage.total_tokens_estimated : null;
  const reviewTokenTotal = reviewUsage ? reviewUsage.total_tokens_reported ?? reviewUsage.total_tokens_estimated : null;
  const warningCount = review ? semanticWarningCount(review) : 0;
  const validationStatus = warningCount ? `${warningCount} semantic warning${warningCount === 1 ? "" : "s"}` : "Validator passed";
  const generatedAt = dossier.generated_at ? new Date(dossier.generated_at).toLocaleString() : "Not reported";
  return (
    <div className="system-grid">
      <section className="system-panel">
        <h2>Dossier status</h2>
        <dl className="facts compact">
          <dt>Validation</dt>
          <dd>{validationStatus}</dd>
          <dt>Last generated</dt>
          <dd>{generatedAt}</dd>
          <dt>Dossier ID</dt>
          <dd>{dossier.dossier_id}</dd>
        </dl>
      </section>
      <section className="system-panel">
        <h2>Preparation coverage</h2>
        <dl className="facts compact">
          <dt>Score</dt>
          <dd>{dossier.coverage_score.coverage_score}%</dd>
          <dt>Found</dt>
          <dd>{dossier.coverage_score.available}</dd>
          <dt>Partial</dt>
          <dd>{dossier.coverage_score.partial}</dd>
          <dt>Missing</dt>
          <dd>{dossier.coverage_score.missing}</dd>
          <dt>Not applicable</dt>
          <dd>{dossier.coverage_score.not_applicable}</dd>
        </dl>
      </section>
      <section className="system-panel">
        <h2>Generation mode</h2>
        <dl className="facts compact">
          <dt>Mode</dt>
          <dd>{usage?.generation_mode ?? "Unknown"}</dd>
          <dt>External LLM</dt>
          <dd>{usage?.external_llm_called ? "Called" : "Not called"}</dd>
          <dt>Provider</dt>
          <dd>{usage?.llm_provider ?? "Unknown"}</dd>
          <dt>Model</dt>
          <dd>{usage?.llm_model ?? "Not reported"}</dd>
          <dt>Tokens</dt>
          <dd>{tokenTotal === null ? "Not reported" : tokenTotal.toLocaleString()}</dd>
        </dl>
      </section>
      <section className="system-panel">
        <h2>Semantic reviewer</h2>
        <dl className="facts compact">
          <dt>Status</dt>
          <dd>{review?.status ?? "Not available"}</dd>
          <dt>Blocking</dt>
          <dd>{review?.blocking ? "Yes" : "No"}</dd>
          <dt>Provider</dt>
          <dd>{review?.reviewer_provider ?? "disabled"}</dd>
          <dt>Warnings</dt>
          <dd>{review ? semanticWarningCount(review) : 0}</dd>
          <dt>Tokens</dt>
          <dd>{reviewTokenTotal === null ? "Not reported" : reviewTokenTotal.toLocaleString()}</dd>
        </dl>
      </section>
      <section className="system-panel wide">
        <h2>Limitations</h2>
        <ul className="limitations">
          {dossier.limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function semanticWarningCount(review: NonNullable<Dossier["semantic_review"]>) {
  return (
    review.unsupported_claims.length +
    review.forbidden_claim_warnings.length +
    review.grounding_warnings.length +
    (review.overclaiming_detected ? 1 : 0) +
    (review.absence_to_risk_violation ? 1 : 0)
  );
}

function List({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="list-section">
      <h2>{title}</h2>
      <div className="list">{children}</div>
    </section>
  );
}

function SourceTypeCoverage({ evidence }: { evidence: EvidenceObject[] }) {
  const items = sourceTypeCoverage(evidence);
  if (!items.length) return null;
  return (
    <div className="source-coverage">
      <span>Source Type Coverage</span>
      <div>
        {items.map((item) => (
          <p key={item.type}>
            <small>{sourceTypeLabel(item.type)}</small>
            <strong>{item.count}</strong>
          </p>
        ))}
      </div>
    </div>
  );
}

function GenerationUsage({ usage }: { usage: Dossier["usage"] }) {
  if (!usage) {
    return null;
  }
  const tokenTotal = usage.total_tokens_reported ?? usage.total_tokens_estimated;
  const tokenLabel = usage.total_tokens_reported === null ? "estimated" : "reported";
  return (
    <div className="source-coverage">
      <span>Generation</span>
      <div>
        <strong>{usage.generation_mode}</strong>
        <p>External LLM: {usage.external_llm_called ? "yes" : "no"}</p>
      </div>
      <p>
        {usage.llm_provider}
        {usage.llm_model ? ` / ${usage.llm_model}` : ""}
      </p>
      <p>
        Tokens: {tokenTotal.toLocaleString()} {tokenLabel}
      </p>
    </div>
  );
}

function SemanticReviewSummary({
  review,
  usage,
}: {
  review: Dossier["semantic_review"];
  usage: Dossier["semantic_review_usage"];
}) {
  if (!review) {
    return null;
  }
  const warningCount =
    review.unsupported_claims.length +
    review.forbidden_claim_warnings.length +
    review.grounding_warnings.length +
    (review.overclaiming_detected ? 1 : 0) +
    (review.absence_to_risk_violation ? 1 : 0);
  const tokenTotal = usage ? usage.total_tokens_reported ?? usage.total_tokens_estimated : null;
  const tokenLabel = usage?.total_tokens_reported === null ? "estimated" : "reported";
  return (
    <div className="source-coverage">
      <span>Semantic Review</span>
      <div>
        <strong>{review.status}</strong>
        <p>External LLM: {usage?.external_llm_called ? "yes" : "no"}</p>
      </div>
      <p>
        {review.reviewer_provider ?? "disabled"}
        {review.reviewer_model ? ` / ${review.reviewer_model}` : ""}
      </p>
      <p>Warnings: {warningCount}</p>
      {tokenTotal !== null ? (
        <p>
          Tokens: {tokenTotal.toLocaleString()} {tokenLabel}
        </p>
      ) : null}
    </div>
  );
}

function EvidenceRefs({
  refs,
  evidenceById,
  onClick,
  compact = false
}: {
  refs: string[];
  evidenceById: Map<string, EvidenceObject>;
  onClick: (evidenceId: string) => void;
  compact?: boolean;
}) {
  if (!refs.length) return null;
  const uniqueRefs = uniqueDisplayRefs(refs, evidenceById);
  return (
    <div className={`evidence-refs${compact ? " compact" : ""}`}>
      {!compact ? <span className="evidence-refs-label">Evidence</span> : null}
      <div className="evidence-ref-list">
        {uniqueRefs.map((ref) => {
          const evidence = evidenceById.get(ref);
          const parts = evidenceRefParts(evidence, ref);
          return (
            <button
              key={ref}
              type="button"
              className="evidence-ref-button"
              aria-label={`Show evidence ${parts.fileName}${parts.locator ? `, ${parts.locator}` : ""}`}
              onClick={() => onClick(ref)}
            >
              <span className="evidence-ref-file">{parts.fileName}</span>
              {parts.locator ? <span className="evidence-ref-page">{parts.locator}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function uniqueDisplayRefs(refs: string[], evidenceById: Map<string, EvidenceObject>) {
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const ref of refs) {
    const evidence = evidenceById.get(ref);
    const parts = evidenceRefParts(evidence, ref);
    const key = evidence
      ? [
          evidence.source_type ?? evidence.evidence_type,
          parts.fileName,
          evidence.source_subtype ?? "",
          parts.locator ?? "",
          evidence.content.trim().replace(/\s+/g, " ")
        ].join("|")
      : ref;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(ref);
  }
  return unique;
}

function EvidenceReview({
  evidence,
  highlightedEvidenceId
}: {
  evidence: EvidenceObject[];
  highlightedEvidenceId: string | null;
}) {
  return (
    <div className="evidence-review">
      <SourceCoveragePanel evidence={evidence} />
      <EvidencePanel evidence={evidence} highlightedEvidenceId={highlightedEvidenceId} />
    </div>
  );
}

function SourceCoveragePanel({ evidence }: { evidence: EvidenceObject[] }) {
  const items = sourceTypeCoverage(evidence);
  const userProvided = evidence.filter((item) => item.source_type === "uploaded_document" || item.source_type === "uploaded_image").length;
  const official = evidence.filter((item) => item.source_type === "official_planning_pdf").length;
  const derived = evidence.filter((item) => item.source_type === "derived").length;
  return (
    <section className="source-coverage-panel">
      <div className="source-coverage-intro">
        <span className="eyebrow">Source coverage</span>
        <h2>Evidence available for this mission case</h2>
        <p>
          This panel shows which kinds of evidence support the dossier. It is not a completeness, compliance, safety,
          or authorization conclusion.
        </p>
      </div>
      <div className="source-coverage-metrics">
        <SummaryCard label="User-provided" value={String(userProvided)} detail="Uploaded case evidence" />
        <SummaryCard label="Official public" value={String(official)} detail="Planning and public sources" />
        <SummaryCard label="System-derived" value={String(derived)} detail="Missing-information records" />
      </div>
      {items.length ? (
        <div className="source-coverage-rows">
          {items.map((item) => (
            <div className="source-coverage-row" key={item.type}>
              <span>{sourceTypeLabel(item.type)}</span>
              <strong>{item.count}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function EvidencePanel({
  evidence,
  highlightedEvidenceId
}: {
  evidence: EvidenceObject[];
  highlightedEvidenceId: string | null;
}) {
  const rows = displayEvidenceRows(evidence);
  return (
    <div className="evidence-list">
      {rows.map(({ item, evidenceIds, duplicateCount }) => (
        <article
          key={evidenceIds.join("|")}
          id={`evidence-${item.evidence_id}`}
          className={`item evidence-item ${highlightedEvidenceId && evidenceIds.includes(highlightedEvidenceId) ? "highlighted" : ""}`}
        >
          <div className="evidence-meta">
            <strong>{evidenceFileName(item)}</strong>
            <span>
              {sourceTypeLabel(item.source_type ?? item.evidence_type)}
              {item.source_subtype ? ` / ${labelize(item.source_subtype)}` : ""}
              {evidenceLocatorLabel(item) ? ` / ${evidenceLocatorLabel(item)}` : ""}
            </span>
          </div>
          <span className={`evidence-type ${item.evidence_type}`}>{evidenceTypeLabel(item.evidence_type)}</span>
          {duplicateCount > 1 ? <span className="evidence-duplicate-note">{duplicateCount} matching evidence records collapsed</span> : null}
          <p>{item.content}</p>
          {evidenceSourceHref(item) ? (
            <a className="source-link" href={evidenceSourceHref(item) ?? undefined} target="_blank" rel="noreferrer">
              Open source{item.page ? ` at page ${item.page}` : ""}
            </a>
          ) : null}
          <details className="advanced-details">
            <summary>Advanced evidence details</summary>
            <dl className="facts compact">
              <dt>Evidence IDs</dt>
              <dd>{evidenceIds.join(", ")}</dd>
              <dt>Source ID</dt>
              <dd>{item.source_id ?? "Not reported"}</dd>
              <dt>Authority</dt>
              <dd>{authorityLabel(item)}</dd>
              <dt>Supports</dt>
              <dd>{item.supports.length ? item.supports.map(labelize).join(", ") : "General context"}</dd>
            </dl>
          </details>
        </article>
      ))}
    </div>
  );
}

function displayEvidenceRows(evidence: EvidenceObject[]) {
  const grouped = new Map<string, EvidenceObject[]>();
  for (const item of evidence) {
    const key = evidenceDisplayKey(item);
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }
  return Array.from(grouped.values()).map((items) => ({
    item: items[0],
    evidenceIds: items.map((item) => item.evidence_id),
    duplicateCount: items.length
  }));
}

function evidenceDisplayKey(evidence: EvidenceObject) {
  return [
    evidence.source_type ?? evidence.evidence_type,
    evidenceFileName(evidence),
    evidence.source_subtype ?? "",
    evidence.page ?? "",
    evidence.content.trim().replace(/\s+/g, " ")
  ].join("|");
}

export default App;
