import json
from typing import Any

import httpx

from app.core.config import settings
from app.models.schemas import (
    ChecklistItem,
    DossierDraft,
    Finding,
    MissingInformationItem,
    ReadinessMatrixItem,
    RiskSignal,
)


class LLMConfigurationError(RuntimeError):
    pass


class LLMGenerationError(RuntimeError):
    pass


class LLMProvider:
    """OpenAI-compatible chat completions client."""

    def __init__(
        self,
        api_key: str | None = settings.llm_api_key,
        base_url: str | None = settings.llm_base_url,
        model: str | None = settings.llm_model,
        response_format: str | None = settings.llm_response_format,
        timeout_seconds: int = settings.llm_timeout_seconds,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.response_format = response_format
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def generate_draft(self, *, system_prompt: str, user_prompt: str) -> DossierDraft:
        if not self.configured:
            raise LLMConfigurationError(
                "LLM is not configured. Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL in .env."
            )
        endpoint = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise LLMGenerationError(
                        f"LLM request failed with HTTP {response.status_code}: {response.text[:500]}"
                    ) from exc
            content = response.json()["choices"][0]["message"]["content"]
            return DossierDraft.model_validate(json.loads(extract_json_object(normalize_message_content(content))))
        except LLMGenerationError:
            raise
        except httpx.HTTPError as exc:
            raise LLMGenerationError(f"LLM request failed: {exc}") from exc
        except (KeyError, json.JSONDecodeError, ValueError) as exc:
            raise LLMGenerationError(f"LLM response was not valid dossier JSON: {exc}") from exc


class MockLLMProvider:
    """Deterministic demo dossier generator used when no external LLM is configured."""

    @property
    def configured(self) -> bool:
        return True

    def generate_draft(self, *, system_prompt: str, user_prompt: str) -> DossierDraft:
        del system_prompt
        try:
            payload = json.loads(user_prompt)
        except json.JSONDecodeError as exc:
            raise LLMGenerationError(f"Mock LLM could not parse generation prompt: {exc}") from exc

        site_context = payload.get("site_context", {})
        taxonomy = payload.get("taxonomy", [])
        evidence = payload.get("evidence", [])
        locked_matrix = payload.get("readiness_matrix_locked") or []
        if not taxonomy:
            raise LLMGenerationError("Mock LLM prompt did not include taxonomy.")
        if not evidence:
            raise LLMGenerationError("Mock LLM prompt did not include evidence.")
        if not locked_matrix:
            raise LLMGenerationError("Mock LLM prompt did not include locked readiness matrix.")

        fallback_ref = evidence[0]["evidence_id"]
        site_refs = [
            item["evidence_id"]
            for item in evidence
            if item.get("source_type") in {"site_profile", "geojson"}
        ] or [fallback_ref]
        official_planning_refs = [
            item["evidence_id"]
            for item in evidence
            if item.get("source_type") == "official_planning_pdf"
        ]
        planning_ref = official_planning_refs[0] if official_planning_refs else fallback_ref
        address = site_context.get("address") or "the selected site"
        commune = site_context.get("commune") or "the commune"

        readiness_matrix = [_mock_matrix_item(item) for item in locked_matrix]
        missing_items = [
            MissingInformationItem(
                item_id=f"missing_{index:03d}",
                category_id=item.category_id,
                description=f"Rule-derived missing information for {item.label.lower()}: {item.summary}",
                evidence_refs=item.evidence_refs,
                recommended_next_action=item.recommended_next_action,
            )
            for index, item in enumerate(readiness_matrix, start=1)
            if item.status in {"missing", "unknown"}
        ][:6]
        checklist_refs = site_refs[:1] if site_refs else [fallback_ref]
        if planning_ref not in checklist_refs:
            checklist_refs.append(planning_ref)

        return DossierDraft(
            building_summary=(
                f"Demo-mode dossier for {address} in {commune}. Retrieved evidence gives enough context "
                "to start a renovation-readiness review, while several technical documents still need human verification."
            ),
            planning_findings=[
                Finding(
                    finding_id="finding_001",
                    title="Retrieved planning context needs review",
                    summary=(
                        "The retrieved planning evidence should be checked against the intended renovation scope "
                        "before permit or design conclusions are made."
                    ),
                    evidence_refs=[planning_ref],
                    source_document=_source_name_for_ref(evidence, planning_ref),
                    page=_page_for_ref(evidence, planning_ref),
                    chunk_id=_chunk_for_ref(evidence, planning_ref),
                )
            ],
            readiness_matrix=readiness_matrix,
            missing_information_checklist=missing_items,
            technical_risk_signals=[
                RiskSignal(
                    signal_id="signal_001",
                    title="Technical records remain incomplete",
                    description=(
                        "Demo mode identifies documentation gaps that should be resolved by qualified reviewers "
                        "before renovation scope, cost, or sequencing decisions."
                    ),
                    evidence_refs=[fallback_ref],
                    priority="medium",
                )
            ],
            inspection_checklist=_mock_checklist(checklist_refs),
            limitations=[
                "Generated in deterministic mock mode without calling an external LLM.",
                "This dossier is for product review and workflow demonstration only.",
                "This is not a final engineering assessment; all engineering, fire-safety, legal, planning, energy, and occupancy conclusions require human review.",
            ],
        )


def create_llm_provider() -> LLMProvider | MockLLMProvider:
    if settings.llm_mock_mode or settings.llm_provider == "mock":
        return MockLLMProvider()
    return LLMProvider()


def _mock_matrix_item(locked_item: dict[str, Any]) -> ReadinessMatrixItem:
    return ReadinessMatrixItem(
        category_id=locked_item["category_id"],
        label=locked_item["label"],
        status=locked_item["status"],
        summary=str(locked_item.get("status_reason") or "Rule-derived readiness status requires human review."),
        evidence_refs=list(locked_item.get("evidence_refs") or []),
        recommended_next_action=str(
            locked_item.get("recommended_next_action_seed") or "Collect and verify supporting evidence."
        ),
    )


def _mock_checklist(evidence_refs: list[str]) -> list[ChecklistItem]:
    tasks = [
        ("check_001", "Verify site identity and access constraints on site.", "The demo evidence may not include parcel-level precision.", "high"),
        ("check_002", "Compare retrieved planning context with the proposed renovation scope.", "Planning evidence needs scope-specific interpretation.", "high"),
        ("check_003", "Request existing drawings and as-built records.", "Layout and intervention planning depend on verified drawings.", "medium"),
        ("check_004", "Schedule structural and envelope walk-throughs.", "Older-building conditions need qualified visual review.", "medium"),
        ("check_005", "Collect MEP, energy, fire-safety, and hazardous-material records.", "These records are common blockers before renovation design work.", "medium"),
    ]
    return [
        ChecklistItem(
            item_id=item_id,
            task=task,
            reason=reason,
            evidence_refs=evidence_refs,
            priority=priority,
        )
        for item_id, task, reason, priority in tasks
    ]


def _source_name_for_ref(evidence: list[dict[str, Any]], evidence_ref: str) -> str | None:
    item = _evidence_for_ref(evidence, evidence_ref)
    return item.get("source_name") if item else None


def _page_for_ref(evidence: list[dict[str, Any]], evidence_ref: str) -> int | None:
    item = _evidence_for_ref(evidence, evidence_ref)
    return item.get("page") if item else None


def _chunk_for_ref(evidence: list[dict[str, Any]], evidence_ref: str) -> str | None:
    item = _evidence_for_ref(evidence, evidence_ref)
    return item.get("chunk_id") if item else None


def _evidence_for_ref(evidence: list[dict[str, Any]], evidence_ref: str) -> dict[str, Any] | None:
    return next((item for item in evidence if item.get("evidence_id") == evidence_ref), None)


def normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("content")
            if isinstance(text, str):
                text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts)
    raise LLMGenerationError("LLM response did not contain text content.")


def extract_json_object(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found in LLM response", stripped, 0)
    return stripped[start : end + 1]
