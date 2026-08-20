# Human Approval Application/API implementation plan

1. Add failing MySQL HTTP tests for create/query/replay/conflict/auth/expiry/concurrency.
2. Add Flyway V6 current/history tables under business namespace.
3. Add schema validator, actor allowlist, domain/application/repository and REST boundary.
4. Run local and full verification, independent review, fix Important findings, hand off.
