import type { DemoSite, Dossier, RetrievedEvidence, SiteContext, SiteGeoJsonResponse } from "../types/dossier";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type GenerateDossierOptions = {
  query?: string;
  includeUploadedDocuments?: boolean;
  maxEvidence?: number;
  forceRefresh?: boolean;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/health");
}

export function getSites(): Promise<DemoSite[]> {
  return request<DemoSite[]>("/api/sites");
}

export function getSiteContext(siteId: string): Promise<SiteContext> {
  return request<SiteContext>(`/api/sites/${siteId}/context`);
}

export function getSiteGeoJson(siteId: string): Promise<SiteGeoJsonResponse> {
  return request<SiteGeoJsonResponse>(`/api/sites/${siteId}/geojson?radius_m=1000`);
}

export function retrieveEvidence(siteId: string, query: string): Promise<RetrievedEvidence> {
  const params = new URLSearchParams({ site_id: siteId, query, limit: "8" });
  return request<RetrievedEvidence>(`/api/evidence?${params.toString()}`);
}

export function uploadDocument(siteId: string, file: File, sourceSubtype?: string): Promise<unknown> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("site_id", siteId);
  if (sourceSubtype) formData.append("source_subtype", sourceSubtype);
  return request<unknown>("/api/documents/upload", {
    method: "POST",
    body: formData
  });
}

export async function generateDossier(siteId: string, options: GenerateDossierOptions = {}): Promise<Dossier> {
  const query = options.query?.trim();
  const payload = await request<{ dossier: Dossier }>("/api/dossiers/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_id: siteId,
      query: query || undefined,
      include_uploaded_documents: options.includeUploadedDocuments ?? true,
      max_evidence: options.maxEvidence ?? 12,
      force_refresh: options.forceRefresh ?? false
    })
  });
  return payload.dossier;
}

export function getDocumentSourceUrl(sourceId: string, page?: number | null): string {
  const pageHash = page ? `#page=${page}` : "";
  return `${API_BASE_URL}/api/sources/${encodeURIComponent(sourceId)}/file${pageHash}`;
}
