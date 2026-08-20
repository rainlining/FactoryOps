# Recorded Demo Scenario

## Requirement: reproducible inspection context

The demo MUST expose a fixed, read-only inspection image and metadata that identify its source path, recorded finding, affected batch and recommended action. It MUST reject arbitrary image paths and MUST label the result as recorded demo data.

### Scenario: load recorded scenario

- **WHEN** the dashboard requests `/api/scenario`
- **THEN** it receives deterministic metadata and a fixed image reference.
