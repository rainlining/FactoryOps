# Executive Demo Packaging

## Requirement: one-command local demo

The repository MUST provide a documented PowerShell entrypoint that starts the local read-only demo server from any repository working directory and prints the dashboard URL.

### Scenario: start demo

- **WHEN** the owner runs the documented script
- **THEN** the server starts on localhost, serves the dashboard and does not modify workflow or dataset files.
