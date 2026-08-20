import pytest
from factoryops_agent_service.demo_dashboard import (
    DashboardInputError,
    render_workflow_dashboard,
)


def _snapshot():
    return {
        "run": {
            "run_id": "RUN-1",
            "status": "SUCCEEDED",
            "incident_id": "QI-1",
            "revision": 3,
            "completed_task_count": 1,
        },
        "tasks": [
            {
                "task_id": "TASK-1",
                "target_agent_role": "quality",
                "status": "SUCCEEDED",
                "attempt_count": 1,
            }
        ],
    }


def test_dashboard_escapes_snapshot_text_and_renders_sections():
    snapshot = _snapshot()
    snapshot["run"]["run_id"] = "<script>alert(1)</script>"
    html = render_workflow_dashboard(snapshot)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "Specialist Tasks" in html
    assert "Decision Chain" in html


@pytest.mark.parametrize("snapshot", [{}, {"run": {}, "tasks": {}}])
def test_dashboard_rejects_invalid_snapshot(snapshot):
    with pytest.raises(DashboardInputError):
        render_workflow_dashboard(snapshot)


def test_dashboard_rejects_malformed_task():
    snapshot = _snapshot()
    snapshot["tasks"] = ["not-an-object"]
    with pytest.raises(DashboardInputError):
        render_workflow_dashboard(snapshot)
