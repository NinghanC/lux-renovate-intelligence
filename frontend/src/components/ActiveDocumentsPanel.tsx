import { Trash2 } from "lucide-react";

import type { SourceRecordPublic } from "../types/dossier";

type DocumentTypeOption = {
  value: string;
  label: string;
};

type ActiveDocumentsPanelProps = {
  documents: SourceRecordPublic[];
  documentTypeOptions: DocumentTypeOption[];
  onRemove: (sourceId: string) => void;
  onTypeChange: (sourceId: string, sourceSubtype: string) => void;
};

export function ActiveDocumentsPanel({
  documents,
  documentTypeOptions,
  onRemove,
  onTypeChange
}: ActiveDocumentsPanelProps) {
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
                  {documentTypeOptions.map((option) => (
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

function sourceRecordFileName(source: SourceRecordPublic) {
  const original = source.metadata?.original_filename;
  return typeof original === "string" && original.trim() ? original : source.display_name;
}

function labelize(value: string) {
  return value.replace(/_/g, " ");
}
