# Workflow Dashboard

## Requirement: snapshot must render as a static, escaped page

`render_workflow_dashboard(snapshot)` MUST return a complete HTML document, escape all snapshot-controlled text, and perform no database, network, or business-state mutation.

### Scenario: malicious text is displayed safely

- **WHEN** a run or task field contains HTML markup
- **THEN** the returned document contains escaped text and no executable copy of that markup.

## Requirement: invalid snapshots fail closed

The renderer MUST reject a missing run object, non-sequence tasks, or malformed task entries with `DashboardInputError`.

### Scenario: malformed snapshot

- **WHEN** `run` is absent or a task is not an object
- **THEN** rendering raises `DashboardInputError` and produces no partial document.
