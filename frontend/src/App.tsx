import { AlertTriangle, Loader2, Play, UploadCloud } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { generateDossier, getSiteContext, getSites, uploadDocument } from "./api/client";
import type { DemoSite, Dossier, EvidenceObject, SiteContext } from "./types/dossier";

type ViewKey = "matrix" | "gaps" | "checklist" | "evidence" | "limitations";

const views: Array<{ key: ViewKey; label: string }> = [
  { key: "matrix", label: "Readiness Matrix" },
  { key: "gaps", label: "Missing Info" },
  { key: "checklist", label: "Site Inspection" },
  { key: "evidence", label: "Evidence Panel" },
  { key: "limitations", label: "Limitations" }
];

function labelize(value: string) {
  return value.replace(/_/g, " ");
}

function evidenceTypeLabel(type: string) {
  if (type === "derived_missing_information") return "Missing information";
  if (type === "planning_document") return "Planning";
  if (type === "uploaded_document") return "Uploaded";
  return labelize(type);
}

function App() {
  const [sites, setSites] = useState<DemoSite[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [siteContext, setSiteContext] = useState<SiteContext | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [activeView, setActiveView] = useState<ViewKey>("matrix");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSite = useMemo(
    () => sites.find((site) => site.site_id === selectedSiteId) ?? null,
    [selectedSiteId, sites]
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dossier generation failed");
    } finally {
      setLoading(false);
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

        <section className="topline">
          <SiteContextBlock siteContext={siteContext} />
          <CompletenessBlock dossier={dossier} />
        </section>

        {dossier ? (
          <>
            <section className="dossier-hero">
              <div>
                <span className="eyebrow">{dossier.dossier_id}</span>
                <h2>Renovation readiness dossier</h2>
                <p>{dossier.building_summary}</p>
              </div>
              <div className="hero-stat">
                <strong>{dossier.coverage_score.coverage_score}%</strong>
                <span>completeness, not risk</span>
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

            <section className="view-panel">{renderView(activeView, dossier)}</section>
          </>
        ) : (
          <section className="empty-state">
            <h2>Ready to generate</h2>
            <p>Generate runs parsing, chunking, hybrid retrieval, rerank, LLM generation, and validation.</p>
          </section>
        )}
      </section>
    </main>
  );
}

function SiteContextBlock({ siteContext }: { siteContext: SiteContext | null }) {
  if (!siteContext) {
    return (
      <section className="panel compact-panel">
        <h2>Site context</h2>
        <p className="empty">Select a demo site.</p>
      </section>
    );
  }

  return (
    <section className="panel compact-panel">
      <h2>Site context</h2>
      <dl className="facts">
        <dt>Address</dt>
        <dd>{siteContext.address}</dd>
        <dt>Commune</dt>
        <dd>{siteContext.commune}</dd>
        <dt>Coordinates</dt>
        <dd>
          {siteContext.coordinates.lat.toFixed(4)}, {siteContext.coordinates.lon.toFixed(4)}
        </dd>
        <dt>Footprint</dt>
        <dd>{siteContext.data_quality.footprint_available ? "available" : "not verified"}</dd>
        <dt>Nearby</dt>
        <dd>{siteContext.nearby_features.length ? siteContext.nearby_features.join(", ") : "unknown"}</dd>
      </dl>
    </section>
  );
}

function CompletenessBlock({ dossier }: { dossier: Dossier | null }) {
  return (
    <section className="panel compact-panel">
      <h2>Dossier completeness</h2>
      {dossier ? (
        <div className="coverage-row">
          <strong>{dossier.coverage_score.coverage_score}%</strong>
          <span>available {dossier.coverage_score.available}</span>
          <span>partial {dossier.coverage_score.partial}</span>
          <span>missing {dossier.coverage_score.missing}</span>
        </div>
      ) : (
        <p className="empty">Calculated from the validated readiness matrix.</p>
      )}
    </section>
  );
}

function renderView(view: ViewKey, dossier: Dossier) {
  if (view === "matrix") {
    return (
      <div className="matrix-grid">
        {dossier.readiness_matrix.map((item) => (
          <article key={item.category_id} className="item">
            <span className={`status ${item.status}`}>{labelize(item.status)}</span>
            <h3>{item.label}</h3>
            <p>{item.summary}</p>
            <small>{item.recommended_next_action}</small>
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
            </article>
          ))}
        </List>
        <List title="Missing Information Checklist">
          {dossier.missing_information_checklist.map((item) => (
            <article key={item.item_id} className="item">
              <h3>{labelize(item.category_id)}</h3>
              <p>{item.description}</p>
              <small>{item.recommended_next_action}</small>
            </article>
          ))}
        </List>
        <List title="Technical Risk Signals">
          {dossier.technical_risk_signals.map((signal) => (
            <article key={signal.signal_id} className="item">
              <span className={`priority ${signal.priority}`}>{signal.priority}</span>
              <h3>{signal.title}</h3>
              <p>{signal.description}</p>
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
            <span className={`priority ${item.priority}`}>{item.priority}</span>
            <h3>{item.task}</h3>
            <p>{item.reason}</p>
            <small>{item.evidence_refs.join(", ")}</small>
          </article>
        ))}
      </div>
    );
  }

  if (view === "evidence") {
    return <EvidencePanel evidence={dossier.evidence} />;
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

function EvidencePanel({ evidence }: { evidence: EvidenceObject[] }) {
  return (
    <div className="evidence-list">
      {evidence.map((item) => (
        <article key={item.evidence_id} className="item evidence-item">
          <div className="evidence-meta">
            <strong>{item.source_name}</strong>
            <span>
              {item.evidence_id}
              {item.page ? ` - page ${item.page}` : ""}
            </span>
          </div>
          <span className={`evidence-type ${item.evidence_type}`}>{evidenceTypeLabel(item.evidence_type)}</span>
          <p>{item.content}</p>
          {item.source_url ? (
            <a href={item.source_url} target="_blank" rel="noreferrer">
              Source
            </a>
          ) : null}
        </article>
      ))}
    </div>
  );
}

export default App;
