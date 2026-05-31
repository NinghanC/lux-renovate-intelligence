import { AlertTriangle, Loader2, Maximize2, Play, X, UploadCloud } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { generateDossier, getDocumentSourceUrl, getSiteContext, getSites, uploadDocument } from "./api/client";
import type { DemoSite, Dossier, EvidenceObject, SiteContext } from "./types/dossier";

type ViewKey = "matrix" | "gaps" | "checklist" | "evidence" | "limitations";

const views: Array<{ key: ViewKey; label: string }> = [
  { key: "matrix", label: "Readiness Matrix" },
  { key: "gaps", label: "Information Gaps" },
  { key: "checklist", label: "Site Inspection" },
  { key: "evidence", label: "Evidence Panel" },
  { key: "limitations", label: "Limitations" }
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
  if (type === "derived_missing_information") return "Missing information";
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
  if (evidence.source_path) return getDocumentSourceUrl(evidence.source_path, evidence.page);
  return null;
}

function evidenceRefLabel(evidence: EvidenceObject | undefined, fallback: string) {
  if (!evidence) return fallback;
  const fileName = evidenceFileName(evidence);
  return evidence.page ? `${fileName} · p.${evidence.page}` : fileName;
}

function evidenceRefParts(evidence: EvidenceObject | undefined, fallback: string) {
  if (!evidence) return { fileName: fallback, page: null as number | null };
  return { fileName: evidenceFileName(evidence), page: evidence.page };
}

function evidenceFileName(evidence: EvidenceObject) {
  const path = evidence.source_path ?? evidence.source_name;
  const rawName = path.split(/[\\/]/).pop() ?? evidence.source_name;
  const uploadedMatch = rawName.match(/^.+?_upload_[a-f0-9]{12}_(.+)$/i);
  return uploadedMatch?.[1] ?? rawName;
}

function scoredCoverageCategories(dossier: Dossier) {
  const coverage = dossier.coverage_score;
  return coverage.available + coverage.partial + coverage.missing + coverage.unknown;
}

function App() {
  const [sites, setSites] = useState<DemoSite[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [siteContext, setSiteContext] = useState<SiteContext | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [activeView, setActiveView] = useState<ViewKey>("matrix");
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null);
  const [mapFullscreen, setMapFullscreen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSite = useMemo(
    () => sites.find((site) => site.site_id === selectedSiteId) ?? null,
    [selectedSiteId, sites]
  );
  const evidenceById = useMemo(
    () => new Map((dossier?.evidence ?? []).map((item) => [item.evidence_id, item])),
    [dossier]
  );

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
    setActiveView("matrix");
    setHighlightedEvidenceId(null);
    setError(null);
    void getSiteContext(selectedSiteId)
      .then((payload) => setSiteContext(payload))
      .catch((err: Error) => setError(err.message));
  }, [selectedSiteId]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !selectedSiteId) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(selectedSiteId, file);
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
      const generated = await generateDossier(selectedSiteId);
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

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">LR</div>
          <div>
            <h1>LuxRenovate</h1>
            <p>Renovation readiness</p>
          </div>
        </div>

        <div className="control-group">
          <label htmlFor="site">Demo site</label>
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

        <div className="actions">
          <label className="icon-button" title="Upload sample document">
            <UploadCloud size={18} />
            <input type="file" accept=".pdf,.txt,.md,.markdown" onChange={handleUpload} />
          </label>
          <button className="primary-button" onClick={handleGenerate} disabled={!selectedSiteId || loading}>
            {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            Generate
          </button>
        </div>

        {uploading ? <p className="quiet">Upload stored locally. It will be parsed during Generate.</p> : null}
      </aside>

      <section className="workspace">
        {error ? (
          <div className="banner">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

          <SiteContextBlock siteContext={siteContext} onOpenMap={() => setMapFullscreen(true)} />

        {dossier ? (
          <>
            <section className="dossier-hero">
              <div>
                <h2>Renovation readiness dossier</h2>
                <p>{dossier.building_summary}</p>
              </div>
              <div className="hero-stat">
                <span>Evidence Coverage Score</span>
                <strong>{dossier.coverage_score.coverage_score}%</strong>
                <small>
                  available {dossier.coverage_score.available} · partial {dossier.coverage_score.partial} · missing{" "}
                  {dossier.coverage_score.missing}
                </small>
                <small>
                  based on {scoredCoverageCategories(dossier)} applicable matrix categories
                  {dossier.coverage_score.not_applicable
                    ? ` · excluded ${dossier.coverage_score.not_applicable} not applicable`
                    : ""}
                  {dossier.coverage_score.unknown ? ` · unknown ${dossier.coverage_score.unknown}` : ""}
                </small>
                {dossier.coverage_score.unknown ? (
                  <small>Unknown is counted as uncovered evidence.</small>
                ) : null}
                <em>Not a risk or compliance score.</em>
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
            <h2>Ready to generate</h2>
            <p>Generate runs parsing, chunking, hybrid retrieval, rerank, LLM generation, and validation.</p>
          </section>
        )}
      </section>
      {mapFullscreen && siteContext ? (
        <MapDialog siteContext={siteContext} onClose={() => setMapFullscreen(false)} />
      ) : null}
    </main>
  );
}

function SiteContextBlock({
  siteContext,
  onOpenMap
}: {
  siteContext: SiteContext | null;
  onOpenMap: () => void;
}) {
  if (!siteContext) {
    return (
      <section className="panel site-context-panel">
        <h2>Site context</h2>
        <p className="empty">Select a demo site.</p>
      </section>
    );
  }

  return (
    <section className="panel site-context-panel">
      <h2>Site context</h2>
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
        <SiteMap siteContext={siteContext} onOpenMap={onOpenMap} />
      </div>
    </section>
  );
}

function SiteMap({
  siteContext,
  onOpenMap,
  fullscreen = false
}: {
  siteContext: SiteContext;
  onOpenMap?: () => void;
  fullscreen?: boolean;
}) {
  const position: [number, number] = [siteContext.coordinates.lat, siteContext.coordinates.lon];

  return (
    <div className={fullscreen ? "site-map fullscreen-map" : "site-map"}>
      {onOpenMap ? (
        <button className="map-expand-button" type="button" onClick={onOpenMap} title="Open full-screen map">
          <Maximize2 size={16} />
        </button>
      ) : null}
      <MapContainer
        key={siteContext.site_id}
        center={position}
        zoom={15}
        scrollWheelZoom={false}
        zoomControl
        className="map-container"
      >
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
      </MapContainer>
    </div>
  );
}

function MapDialog({ siteContext, onClose }: { siteContext: SiteContext; onClose: () => void }) {
  return (
    <div className="map-dialog-backdrop" role="dialog" aria-modal="true" aria-label="Site map">
      <div className="map-dialog">
        <div className="map-dialog-header">
          <div>
            <h2>Site map</h2>
            <p>
              {siteContext.address} · {siteContext.coordinates.lat.toFixed(4)},{" "}
              {siteContext.coordinates.lon.toFixed(4)}
            </p>
          </div>
          <button className="map-close-button" type="button" onClick={onClose} title="Close map">
            <X size={18} />
          </button>
        </div>
        <SiteMap siteContext={siteContext} fullscreen />
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
        <List title="Planning Evidence Findings">
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
        <List title="Missing Information Checklist">
          {dossier.missing_information_checklist.map((item) => (
            <article key={item.item_id} className="item">
              <h3>{labelize(item.category_id)}</h3>
              <p>{item.description}</p>
              <small>{item.recommended_next_action}</small>
              <EvidenceRefs refs={item.evidence_refs} evidenceById={evidenceById} onClick={onEvidenceRefClick} />
            </article>
          ))}
        </List>
        <List title="Technical Risk Signals">
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

  if (view === "evidence") {
    return <EvidencePanel evidence={dossier.evidence} highlightedEvidenceId={highlightedEvidenceId} />;
  }

  return (
    <ul className="limitations">
      {dossier.limitations.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
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
  return (
    <div className="evidence-refs">
      <span className="evidence-refs-label">Refs</span>
      <div className="evidence-ref-list">
        {refs.map((ref) => {
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
              {parts.page ? <span className="evidence-ref-page">p.{parts.page}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function EvidencePanel({
  evidence,
  highlightedEvidenceId
}: {
  evidence: EvidenceObject[];
  highlightedEvidenceId: string | null;
}) {
  return (
    <div className="evidence-list">
      {evidence.map((item) => (
        <article
          key={item.evidence_id}
          id={`evidence-${item.evidence_id}`}
          className={`item evidence-item ${highlightedEvidenceId === item.evidence_id ? "highlighted" : ""}`}
        >
          <div className="evidence-meta">
            <strong>{evidenceFileName(item)}</strong>
            <span>{item.page ? `page ${item.page}` : evidenceTypeLabel(item.evidence_type)}</span>
          </div>
          <span className={`evidence-type ${item.evidence_type}`}>{evidenceTypeLabel(item.evidence_type)}</span>
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

export default App;
