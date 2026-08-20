# FactoryOps Dashboard UI

## Requirement: static Snapshot must be loadable and safe

The dashboard MUST render the bundled demo Snapshot on first load, accept a user-selected JSON Snapshot, reject malformed top-level data, and render user-controlled text as text rather than HTML.

### Scenario: load a valid Snapshot file

- **WHEN** the user selects a valid JSON Snapshot
- **THEN** the dashboard updates Run summary, task rows and decision chain without navigating away.

### Scenario: reject malformed data

- **WHEN** the selected file is not a Snapshot object
- **THEN** the dashboard keeps the current view and shows a concise error state.

## Requirement: read-only presentation

The dashboard MUST expose no control that mutates approval, risk, task, run or business-action state.
