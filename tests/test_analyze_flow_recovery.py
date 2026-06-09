from app.analyze_flow import new_analyze_flow_state
from app.analyze_flow_persistence import sanitize_flow_payload, state_from_persisted_dict, state_to_persisted_dict


def test_sanitize_flow_payload_strips_prompt_fields() -> None:
    cleaned = sanitize_flow_payload(
        {
            "summary": {"prompt_body": "secret", "workspace": {"name": "Example Lab"}},
            "steps": [],
        }
    )
    assert "prompt_body" not in cleaned.get("summary", {})
    assert cleaned["summary"]["workspace"]["name"] == "Example Lab"


def test_flow_state_roundtrip() -> None:
    state = new_analyze_flow_state()
    state.workspace_id = "ws-1"
    state.website_url = "https://www.example.com"
    state.run_label = "Example Lab test"
    state.summary = {"workspace": {"name": "Example Lab"}, "recommendations": {"total": 12}}
    state.parent_run_id = "parent-1"
    state.rerun_type = "competitor_discovery"
    restored = state_from_persisted_dict(state_to_persisted_dict(state))
    assert restored.workspace_id == "ws-1"
    assert restored.parent_run_id == "parent-1"
    assert restored.rerun_type == "competitor_discovery"
    assert restored.summary["recommendations"]["total"] == 12
