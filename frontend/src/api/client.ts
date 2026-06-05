import type { DemoSite, Dossier, RetrievedEvidence, SiteContext, SiteGeoJsonResponse, SourceRecordPublic } from "../types/dossier";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_AUTH_TOKEN = import.meta.env.VITE_API_AUTH_TOKEN ?? "";
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 240000);

function authHeaders(headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  if (API_AUTH_TOKEN) {
    result.set("X-API-Key", API_AUTH_TOKEN);
  }
  return result;
}

export type GenerateDossierOptions = {
  query?: string;
  includeUploadedDocuments?: boolean;
  maxEvidence?: number;
  forceRefresh?: boolean;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: authHeaders(options?.headers),
      signal: controller.signal
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(API_TIMEOUT_MS / 1000)} seconds.`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
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

export function getActiveDocuments(siteId: string): Promise<SourceRecordPublic[]> {
  const params = new URLSearchParams({ site_id: siteId });
  return request<SourceRecordPublic[]>(`/api/documents/active?${params.toString()}`);
}

export function removeActiveDocument(siteId: string, sourceId: string): Promise<SourceRecordPublic[]> {
  const params = new URLSearchParams({ site_id: siteId });
  return request<SourceRecordPublic[]>(`/api/documents/active/${encodeURIComponent(sourceId)}?${params.toString()}`, {
    method: "DELETE"
  });
}

export function updateActiveDocumentType(siteId: string, sourceId: string, sourceSubtype: string): Promise<SourceRecordPublic[]> {
  const params = new URLSearchParams({ site_id: siteId });
  return request<SourceRecordPublic[]>(`/api/documents/active/${encodeURIComponent(sourceId)}?${params.toString()}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_subtype: sourceSubtype })
  });
}

export function uploadDocument(siteId: string, file: File, sourceSubtype?: string, replaceActiveDocuments = false): Promise<unknown> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("site_id", siteId);
  if (sourceSubtype) formData.append("source_subtype", sourceSubtype);
  formData.append("replace_active_documents", String(replaceActiveDocuments));
  return request<unknown>("/api/documents/upload", {
    method: "POST",
    body: formData
  });
}

export function uploadDocuments(siteId: string, files: File[], sourceSubtype?: string, replaceActiveDocuments = false): Promise<unknown> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("site_id", siteId);
  if (sourceSubtype) formData.append("source_subtype", sourceSubtype);
  formData.append("replace_active_documents", String(replaceActiveDocuments));
  return request<unknown>("/api/documents/upload-batch", {
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

export async function getDocumentSourceBlobUrl(sourceId: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/sources/${encodeURIComponent(sourceId)}/file`, {
    headers: authHeaders()
  });
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
  return URL.createObjectURL(await response.blob());
}
