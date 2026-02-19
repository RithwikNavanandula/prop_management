# Property Management V2 - Architecture Enhancement (In-Place Upgrade)

## 1. Approach
This plan enhances the current FastAPI modular monolith and existing database schema. It does not replace existing modules.

Current modules retained:
- `properties`, `leasing`, `billing`, `maintenance`, `compliance`, `workflow`, `utilities`, `dashboard`, `system`

New capability layers added on top:
- Country policy engine
- Multi-currency ledger + FX snapshots
- Event outbox for reliable domain events
- Workflow runtime (instances/tasks)
- Document lifecycle management (versions/obligations)
- KPI mart (daily fact table)

## 2. Capability Layer Design

### 2.1 Country Policy Engine
- Table: `country_policies`
- Purpose: Resolve country/state-specific behavior for tax/legal/workflow/compliance actions.
- Resolution dimensions:
  - tenant org
  - country code
  - optional state code
  - policy area
  - entity type
  - action name
  - effective date window
  - priority

### 2.2 Multi-Currency Ledger
- Tables: `fx_rate_snapshots`, `multi_currency_ledger_entries`
- Existing `exchange_rates_daily` is preserved and used as source.
- Every invoice/payment/revaluation can write ledger entries with:
  - txn currency/amount
  - base currency/amount
  - fx rate used

### 2.3 Event Outbox
- Table: `event_outbox`
- Event producer is executed inside same DB transaction as business write.
- Events can later be consumed by worker(s) for notifications, workflows, and integrations.
- Event examples:
  - `lease.created`
  - `invoice.created`
  - `payment.received`
  - `document.uploaded`
  - `workflow.task.completed`

### 2.4 Workflow Runtime
- Tables: `workflow_instances`, `workflow_tasks`
- Existing workflow definition tables are preserved.
- Runtime supports:
  - create instance from definition
  - assign approval tasks
  - complete tasks and auto-close instance

### 2.5 Document Lifecycle
- Tables: `document_versions`, `document_obligations`
- Every created/uploaded compliance document stores v1 in versions.
- Optional expiry creates obligation automatically.
- Supports additional uploaded versions while preserving history.

### 2.6 KPI Mart
- Table: `kpi_daily_facts`
- Daily denormalized metrics for dashboard speed and consistency.
- Current implementation seeds key tenant-level KPIs:
  - occupancy rate
  - total invoiced
  - total collected
  - open maintenance requests

## 3. Runtime Data Flow
1. Business write (e.g., create invoice).
2. Domain write commits core record(s).
3. Ledger/event/versions/obligations records are written in same unit of work.
4. Dashboard mart rebuild runs scheduled or on demand.
5. Integrations consume outbox asynchronously.

## 4. Security and Scope
- Tenant scoping remains primary filter.
- Admin-only routes for policy/outbox control remain under `system` permissions.
- New workflow/document/billing APIs enforce tenant filters.

## 5. Non-Functional Improvements
- Better auditability: explicit versions, obligations, and outbox records.
- Better global readiness: policy resolution + FX snapshots.
- Better extensibility: event-driven orchestration without service split yet.

## 6. Next Step (Phase 2)
- Add outbox dispatcher worker and retry/backoff policies.
- Add UI for country policy builder and obligations board.
- Add region/property-scoped KPI materialization and scheduled refresh.
- Add analytics warehouse sync from KPI mart and outbox stream.
