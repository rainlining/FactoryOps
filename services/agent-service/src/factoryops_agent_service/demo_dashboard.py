from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape


class DashboardInputError(ValueError):
    pass


def render_workflow_dashboard(snapshot: Mapping[str, object]) -> str:
    if not isinstance(snapshot, Mapping) or not isinstance(
        snapshot.get("run"), Mapping
    ):
        raise DashboardInputError("snapshot.run is required")
    run = snapshot["run"]
    tasks = snapshot.get("tasks", [])
    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)):
        raise DashboardInputError("snapshot.tasks must be a sequence")
    run_id = _text(run.get("run_id"), "unknown")
    status = _text(run.get("status"), "UNKNOWN")
    status_class = {
        "SUCCEEDED": "status succeeded",
        "FAILED": "status failed",
        "RUNNING": "status running",
    }.get(status, "status")
    rows = "".join(_task_row(task) for task in tasks)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FactoryOps Workflow {escape(run_id)}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f4f6f8;color:#17202a;margin:0;padding:32px}}
main{{max-width:1100px;margin:auto}} header,section{{background:white;border:1px solid #d9e0e6;border-radius:8px;padding:20px;margin-bottom:16px}}
.eyebrow{{font-size:12px;text-transform:uppercase;color:#61707d;letter-spacing:.08em}} h1{{margin:6px 0 0}}
.status{{display:inline-block;padding:4px 10px;border-radius:999px;background:#e8eef3;font-weight:600}} table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;padding:10px;border-bottom:1px solid #e6ebef}} th{{color:#61707d;font-size:12px;text-transform:uppercase}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}} .value{{font-size:18px;font-weight:650;margin-top:5px}}
@media(max-width:600px){{body{{padding:16px}}}}
</style></head><body><main>
<header><div class="eyebrow">FactoryOps workflow</div><h1>{escape(run_id)}</h1><p class="{status_class}">{escape(status)}</p></header>
<section><div class="grid">{_card("Incident", run.get("incident_id"))}{_card("Revision", run.get("revision"))}{_card("Tasks", len(tasks))}{_card("Completed", run.get("completed_task_count"))}</div></section>
<section><h2>Specialist Tasks</h2><table><thead><tr><th>Task</th><th>Role</th><th>Status</th><th>Attempt</th></tr></thead><tbody>{rows or '<tr><td colspan="4">Not available</td></tr>'}</tbody></table></section>
<section><h2>Decision Chain</h2><div class="grid">{_card("Coordinator", _value(snapshot.get("coordinator"), "status"))}{_card("Fusion", _value(snapshot.get("fusion"), "proposed_action"))}{_card("Risk", _value(snapshot.get("risk"), "decision"))}{_card("Approval", _value(snapshot.get("approval"), "status"))}</div></section>
</main></body></html>"""


def _task_row(task: object) -> str:
    if not isinstance(task, Mapping):
        raise DashboardInputError("task must be an object")
    return (
        "<tr>"
        + "".join(
            f"<td>{escape(_text(task.get(field), 'Not available'))}</td>"
            for field in ("task_id", "target_agent_role", "status", "attempt_count")
        )
        + "</tr>"
    )


def _card(label: str, value: object) -> str:
    return f'<div><div class="eyebrow">{escape(label)}</div><div class="value">{escape(_text(value, "Not available"))}</div></div>'


def _value(value: object, field: str) -> object:
    return value.get(field) if isinstance(value, Mapping) else None


def _text(value: object, default: str) -> str:
    return default if value is None else str(value)
