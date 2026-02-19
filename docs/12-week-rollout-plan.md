# 12-Week Enhancement Rollout Plan

## Principle
Upgrade the current PMS incrementally with zero module rewrites and controlled rollout by feature flags.

## Week 1-2: Foundation Schema + APIs
- Deploy new tables:
  - policies, outbox, FX snapshots, ledger, workflow runtime, document lifecycle, KPI mart
- Enable APIs:
  - policy CRUD/resolve
  - outbox visibility
  - FX rates/snapshots/revaluation
- Add smoke tests for new endpoints.

## Week 3-4: Event-Driven Core Flows
- Emit outbox events from:
  - lease create
  - invoice create
  - payment create
  - maintenance request/work-order create
  - compliance document upload/version
  - workflow task completion
- Add outbox operational dashboard (pending/failed/retry counts).

## Week 5-6: Workflow Runtime and Approvals
- Onboard 3 real workflows:
  - invoice approval
  - lease renewal approval
  - maintenance escalation
- Add SLA timers and assignee views.
- Add audit reports for instance/task lifecycle.

## Week 7-8: Document Governance
- Enforce version history as required path for regulated docs.
- Auto-generate obligations on expiry.
- Add alerting pipeline for upcoming obligations.
- Add retention and archival policy config.

## Week 9-10: KPI Mart and Executive Analytics
- Schedule daily KPI build jobs.
- Backfill last 90 days where feasible.
- Switch dashboard heavy cards to KPI mart reads.
- Validate KPI parity vs transactional reports.

## Week 11: Hardening and Performance
- Add indexes and query tuning based on production cardinality.
- Load test high-volume endpoints (billing, dashboard, workflow tasks).
- Introduce idempotency keys for critical writes.

## Week 12: Go-Live Stabilization
- Feature-flag rollout per tenant/region.
- Monitoring and SLOs:
  - API p95 latency
  - outbox publish lag
  - workflow task cycle time
  - KPI refresh completion time
- Runbook + rollback playbooks finalized.

## Exit Criteria
- No critical regressions in existing module behavior.
- >= 99% successful daily KPI rebuild jobs.
- Outbox pending queue under agreed threshold.
- All priority compliance documents tracked with versions and obligations.
