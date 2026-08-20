# Dashboard Live Query

## Requirement: read-only snapshot API

The local demo server MUST expose `GET /api/snapshot` as JSON, serve the dashboard assets, reject non-GET mutation methods, and never modify workflow state.

### Scenario: API-backed first load

- **WHEN** the dashboard opens while the local server is available
- **THEN** it renders the API Snapshot and labels the source as API.

### Scenario: API unavailable

- **WHEN** the API request fails
- **THEN** the dashboard keeps a usable fallback view and shows a non-blocking source/error notice.
