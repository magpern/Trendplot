from __future__ import annotations

import copy
from typing import Any

from app.analyze_flow import AnalyzeFlowState


_SENSITIVE_KEY_PARTS = ("prompt", "api_key", "password", "token", "secret")


def sanitize_flow_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                continue
            cleaned[key] = sanitize_flow_payload(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_flow_payload(item) for item in value[:200]]
    return value


def state_to_persisted_dict(state: AnalyzeFlowState) -> dict[str, Any]:
    payload = state.as_dict()
    payload["summary"] = sanitize_flow_payload(payload.get("summary") or {})
    payload["steps"] = sanitize_flow_payload(payload.get("steps") or [])
    return sanitize_flow_payload(payload)


def state_from_persisted_dict(payload: dict[str, Any]) -> AnalyzeFlowState:
    from app.analyze_flow import AnalyzeFlowStep, PRODUCT_ANALYZE_STEP_KEYS, new_analyze_flow_state

    state = new_analyze_flow_state()
    state.job_id = str(payload.get("job_id") or state.job_id)
    state.workspace_id = payload.get("workspace_id")
    state.overall_status = str(payload.get("overall_status") or state.overall_status)
    state.cancel_requested = bool(payload.get("cancel_requested"))
    state.summary = copy.deepcopy(payload.get("summary") or {})
    state.parent_run_id = payload.get("parent_run_id")
    state.rerun_type = payload.get("rerun_type")
    state.website_url = payload.get("website_url")
    state.run_label = payload.get("run_label")
    state.request_payload = copy.deepcopy(payload.get("request_payload") or {})
    state.prior_summary = copy.deepcopy(payload.get("prior_summary") or {})
    steps = payload.get("steps") or []
    if steps:
        state.steps = [
            AnalyzeFlowStep(
                key=str(item.get("key") or ""),
                label=str(item.get("label") or ""),
                status=str(item.get("status") or "queued"),
                started_at=item.get("started_at"),
                completed_at=item.get("completed_at"),
                duration_seconds=item.get("duration_seconds"),
                message=str(item.get("message") or ""),
                error=item.get("error"),
                warnings=list(item.get("warnings") or []),
                progress_current=item.get("progress_current"),
                progress_total=item.get("progress_total"),
                progress_label=item.get("progress_label"),
                details=dict(item.get("details") or {}),
                timing_note=item.get("timing_note"),
            )
            for item in steps
            if item.get("key")
        ]
    state.steps = [step for step in state.steps if step.key in PRODUCT_ANALYZE_STEP_KEYS]
    return state
