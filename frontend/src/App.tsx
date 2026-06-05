import { AlertTriangle, Loader2, MapPinPlus, Maximize2, Play, SlidersHorizontal, Trash2, X, UploadCloud } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMapEvents } from "react-leaflet";
import {
  generateDossier,
  getDocumentSourceUrl,
  getSiteContext,
  getSiteGeoJson,
  getSites,
  uploadDocument
} from "./api/client";
import type { DemoSite, Dossier, EvidenceObject, GeoJsonFeature, SiteContext, SiteGeoJsonResponse } from "./types/dossier";

type ViewKey = "documents" | "evidence" | "matrix" | "gaps" | "checklist" | "system";

type DrawnMapPoint = {
  id: string;
  lat: number;
  lon: number;
  distance_m: number;
};

const views: Array<{ key: ViewKey; label: string }> = [
  { key: "documents", label: "Documents" },
  { key: "evidence", label: "Evidence" },
  { key: "matrix", label: "Mission Readiness" },
  { key: "gaps", label: "Expert Validation" },
  { key: "checklist", label: "Mission Checklist" },
  { key: "system", label: "System" }
];

const statusLabels: Record<string, string> = {
  available: "Available",
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
  if (evidence.source_id && ["official_planning_pdf", "uploaded_document", "uploaded_image"].includes(evidence.source_type ?? "")) {
    return getDocumentSourceUrl(evidence.source_id, evidence.page);
  }
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

function App() {
  const [sites, setSites] = useState<DemoSite[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [siteContext, setSiteContext] = useState<SiteContext | null>(null);
  const [siteGeoJson, setSiteGeoJson] = useState<SiteGeoJsonResponse | null>(null);
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
  const [advancedOpen, setAdvancedOpen] = useState(false);
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
    void getSites()
      .then((payload) => {
        setSites(payload);
        setSelectedSiteId(payload[0]?.site_id ?? "");
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedSiteId) return;
    setDossier(null);
    setSiteGeoJson(null);
    setMapDrawingEnabled(false);
    setActiveView("matrix");
    setHighlightedEvidenceId(null);
    setError(null);
    void Promise.all([getSiteContext(selectedSiteId), getSiteGeoJson(selectedSiteId)])
      .then(([context, geojson]) => {
        setSiteContext(context);
        setSiteGeoJson(geojson);
      })
      .catch((err: Error) => setError(err.message));
  }, [selectedSiteId]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !selectedSiteId) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(selectedSiteId, file, uploadSubtype || undefined);
      setUploadPanelOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleGenerate() {
    if (!selectedSiteId) return;
    setLoading(true);
    setError(null);
    try {
      const generated = await generateDossier(selectedSiteId, {
        query: investigationQuestion,
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

  function handleEvidenceRefClick(evidenceId: string) {
    const evidence = evidenceById.get(evidenceId);
    const href = evidenceSourceHref(evidence);
    setActiveView("evidence");
    setHighlightedEvidenceId(evidenceId);
    window.setTimeout(() => {
      document.getElementById(`evidence-${evidenceId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
    if (href) {
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
            {sites.map((site) => (
              <option key={site.site_id} value={site.site_id}>
                {site.display_name}
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
          >
            <SlidersHorizontal size={16} />
            Advanced options
          </button>
          {advancedOpen ? (
            <div className="advanced-fields">
              <label className="field">
                <span>Investigation question</span>
                <textarea
                  rows={3}
                  value={investigationQuestion}
                  onChange={(event) => setInvestigationQuestion(event.target.value)}
                  placeholder="Environmental authorization, HVAC records, asbestos inventory, survey needs..."
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
            onClick={() => setUploadPanelOpen((open) => !open)}
            disabled={!selectedSiteId || uploading}
          >
            <UploadCloud size={18} />
          </button>
          <button className="primary-button" onClick={handleGenerate} disabled={!selectedSiteId || loading}>
            {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            Generate dossier
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
              <input type="file" accept=".pdf,.txt,.md,.markdown" onChange={handleUpload} disabled={uploading} />
            </label>
          </div>
        ) : null}

        {uploading ? <p className="quiet">Case document stored locally. It will be parsed during Generate.</p> : null}
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

        {dossier ? (
          <>
            <section className="dossier-hero">
              <div>
                <h2>Mission readiness dossier</h2>
                <p>{dossier.building_summary}</p>
              </div>
              <div className="hero-side">
                <div className="hero-stat">
                  <span>Case-file Evidence Coverage</span>
                  <strong>{dossier.coverage_score.coverage_score}%</strong>
                  <small>
                    available {dossier.coverage_score.available} / partial {dossier.coverage_score.partial} / missing{" "}
                    {dossier.coverage_score.missing}
                  </small>
                  <small>
                    based on {scoredCoverageCategories(dossier)} applicable matrix categories
                    {dossier.coverage_score.not_applicable
                      ? ` / excluded ${dossier.coverage_score.not_applicable} not applicable`
                      : ""}
                    {dossier.coverage_score.unknown ? ` / unknown ${dossier.coverage_score.unknown}` : ""}
                  </small>
                  {dossier.coverage_score.unknown ? (
                    <small>Unknown is counted as uncovered evidence.</small>
                  ) : null}
                  <em>Not a risk, safety, authorization, or compliance score.</em>
                </div>
                <SourceTypeCoverage evidence={dossier.evidence} />
                <GenerationUsage usage={dossier.usage} />
                <SemanticReviewSummary
                  review={dossier.semantic_review}
                  usage={dossier.semantic_review_usage}
                />
              </div>
            </section>

            <nav className="tabs" aria-label="Dossier views">
              {views.map((view) => (
                <button
                  key={view.key}
                  className={activeView === view.key ? "active" : ""}
                  onClick={() => setActiveView(view.key)}
                >
                  {view.label}
                </button>
              ))}
            </nav>

            <section className="view-panel">
              {renderView(activeView, dossier, evidenceById, handleEvidenceRefClick, highlightedEvidenceId)}
            </section>
          </>
        ) : (
          <section className="empty-state">
            <h2>Start a mission preparation case</h2>
            <p>Select the Luxembourg demo case, add case documents if needed, then generate a traceable mission readiness dossier.</p>
          </section>
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
          <button className="map-expand-button" type="button" onClick={onOpenMap} title="Open full-screen map">
            <Maximize2 size={16} />
          </button>
        ) : null}
        <button
          className={`map-tool-button ${drawingEnabled ? "active" : ""}`}
          type="button"
          onClick={onToggleDrawing}
          title="Add map point"
        >
          <MapPinPlus size={16} />
        </button>
        {drawnPoints.length ? (
          <button className="map-tool-button" type="button" onClick={onClearDrawnPoints} title="Clear map points">
            <Trash2 size={16} />
          </button>
        ) : null}
      </div>
      <MapContainer
        key={siteContext.site_id}
        center={position}
        zoom={15}
        scrollWheelZoom={false}
        zoomControl
        className="map-container"
      >
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
          <button className="map-close-button" type="button" onClick={onClose} title="Close map">
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
  highlightedEvidenceId: string | null
) {
  if (view === "documents") {
    return <DocumentInventory evidence={dossier.evidence} />;
  }

  if (view === "evidence") {
    return <EvidencePanel evidence={dossier.evidence} highlightedEvidenceId={highlightedEvidenceId} />;
  }

  if (view === "matrix") {
    return (
      <div className="matrix-grid">
        {dossier.readiness_matrix.map((item) => (
          <article key={item.category_id} className="item">
            <span className={`status ${item.status}`}>{statusLabel(item.status)}</span>
            <h3>{item.label}</h3>
            <p>{item.summary}</p>
            <small>{item.recommended_next_action}</small>
            <EvidenceRefs refs={item.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} />
          </article>
        ))}
      </div>
    );
  }

  if (view === "gaps") {
    return (
      <div className="split-view">
        <List title="Public Context Findings">
          {dossier.planning_findings.map((finding) => (
            <article key={finding.finding_id} className="item">
              <h3>{finding.title}</h3>
              <p>{finding.summary}</p>
              <small>
                {finding.source_document ?? "source"}
                {finding.page ? ` - page ${finding.page}` : ""}
              </small>
              <EvidenceRefs refs={finding.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} />
            </article>
          ))}
        </List>
        <List title="Missing Mission-Critical Documents">
          {dossier.missing_information_checklist.map((item) => (
            <article key={item.item_id} className="item">
              <h3>{labelize(item.category_id)}</h3>
              <p>{item.description}</p>
              <small>{item.recommended_next_action}</small>
              <EvidenceRefs refs={item.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} />
            </article>
          ))}
        </List>
        <List title="Items Requiring Expert Validation">
          {dossier.technical_risk_signals.map((signal) => (
            <article key={signal.signal_id} className="item">
              <span className={`priority ${signal.priority}`}>Priority: {priorityLabel(signal.priority)}</span>
              <h3>{signal.title}</h3>
              <p>{signal.description}</p>
              <EvidenceRefs refs={signal.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} />
            </article>
          ))}
        </List>
      </div>
    );
  }

  if (view === "checklist") {
    return (
      <div className="list">
        {dossier.inspection_checklist.map((item) => (
          <article key={item.item_id} className="item">
            <span className={`priority ${item.priority}`}>Priority: {priorityLabel(item.priority)}</span>
            <h3>{item.task}</h3>
            <p>{item.reason}</p>
            <EvidenceRefs refs={item.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} />
          </article>
        ))}
      </div>
    );
  }

  return <SystemTransparency dossier={dossier} />;
}

type DocumentInventoryRow = {
  key: string;
  fileName: string;
  detectedType: string;
  status: string;
  evidenceCount: number;
  supports: string[];
  authority: string;
  used: boolean;
};

function DocumentInventory({ evidence }: { evidence: EvidenceObject[] }) {
  const rows = documentInventoryRows(evidence);
  if (!rows.length) {
    return (
      <section className="empty-state inline-empty">
        <h2>Case document inventory</h2>
        <p>No case documents have been parsed into dossier evidence yet.</p>
      </section>
    );
  }
  return (
    <div className="inventory-table-wrap">
      <table className="inventory-table">
        <thead>
          <tr>
            <th>File or source</th>
            <th>Detected type</th>
            <th>Status</th>
            <th>Evidence</th>
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
        fileName: evidenceFileName(first),
        detectedType: detectedTypeLabel(detectedTypes, first),
        status: first.source_type === "derived" ? "System-derived" : "Parsed",
        evidenceCount: items.length,
        supports,
        authority: authorityLabel(first),
        used: items.some((item) => item.evidence_id.startsWith("ev_"))
      };
    })
    .sort((left, right) => left.fileName.localeCompare(right.fileName));
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
  return (
    <div className="system-grid">
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
  onClick
}: {
  refs: string[];
  evidenceById: Map<string, EvidenceObject>;
  onClick: (evidenceId: string) => void;
}) {
  if (!refs.length) return null;
  const uniqueRefs = uniqueDisplayRefs(refs, evidenceById);
  return (
    <div className="evidence-refs">
      <span className="evidence-refs-label">Refs</span>
      <div className="evidence-ref-list">
        {uniqueRefs.map((ref) => {
          const evidence = evidenceById.get(ref);
          const parts = evidenceRefParts(evidence, ref);
          return (
            <button
              key={ref}
              type="button"
              className="evidence-ref-button"
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
