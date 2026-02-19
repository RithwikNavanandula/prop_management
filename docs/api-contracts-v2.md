# API Contracts v2 (Enhancement Layer)

## System - Policy and Outbox

### GET `/api/system/country-policies`
Query:
- `country_code`, `policy_area`, `entity_type`, `action_name`
Response:
- `{ total, items[] }`

### POST `/api/system/country-policies`
Body:
```json
{
  "country_code": "AE",
  "state_code": "DU",
  "policy_area": "tax",
  "entity_type": "Invoice",
  "action_name": "post_invoice",
  "priority": 10,
  "rules_json": {"vat_rate": 5.0},
  "effective_from": "2026-01-01"
}
```

### POST `/api/system/country-policies/resolve`
Body:
```json
{
  "country_code": "AE",
  "state_code": "DU",
  "policy_area": "tax",
  "entity_type": "Invoice",
  "action_name": "post_invoice",
  "effective_on": "2026-02-18"
}
```
Response:
- `{ matched: true|false, policy: {...}|null }`

### GET `/api/system/event-outbox`
Query:
- `status`, `event_type`, `limit`
Response:
- `{ total, items[] }`

### POST `/api/system/event-outbox/{event_id}/mark-published`
Response:
- updated outbox event row

## Billing - FX and Ledger

### GET `/api/billing/fx-rates`
Query:
- `from_currency`, `to_currency`, `rate_date`

### POST `/api/billing/fx-rates`
Body:
```json
{
  "rate_date": "2026-02-18",
  "from_currency": "AED",
  "to_currency": "USD",
  "rate": 0.2723,
  "source": "Manual"
}
```

### POST `/api/billing/fx-snapshots/generate`
Body:
```json
{"snapshot_date": "2026-02-18"}
```
Response:
- `{ snapshot_date, created }`

### GET `/api/billing/fx-snapshots`
Query:
- `snapshot_date`, `from_currency`, `to_currency`

### POST `/api/billing/invoices/{inv_id}/revalue`
Body:
```json
{"as_of": "2026-02-18"}
```
Response:
- `{ invoice: {...}, gain_loss }`

### GET `/api/billing/ledger-entries`
Query:
- `reference_type`, `reference_id`

## Workflow - Runtime

### GET `/api/workflow/instances`
Query:
- `status`, `entity_type`, `entity_id`

### POST `/api/workflow/instances`
Body:
```json
{
  "workflow_definition_id": 3,
  "entity_type": "Invoice",
  "entity_id": 9001,
  "create_initial_task": true,
  "first_task_name": "Finance Approval",
  "assigned_role": "manager"
}
```

### GET `/api/workflow/instances/{instance_id}`
Response includes instance + `tasks[]`.

### GET `/api/workflow/instances/{instance_id}/tasks`

### POST `/api/workflow/instances/{instance_id}/tasks`
Body:
```json
{"task_name": "Legal Review", "assigned_role": "legal"}
```

### PUT `/api/workflow/tasks/{task_id}`
Partial update body for assignment/status metadata.

### POST `/api/workflow/tasks/{task_id}/complete`
Body:
```json
{"decision": "Approved", "decision_notes": "All checks passed"}
```

## Compliance - Document Lifecycle

### GET `/api/compliance/documents/{doc_id}/versions`

### POST `/api/compliance/documents/{doc_id}/versions/upload`
Multipart form:
- `file`: binary
- `notes`: optional

### GET `/api/compliance/obligations`
Query:
- `status`, `obligation_type`, `due_before`

### POST `/api/compliance/obligations`
Body:
```json
{
  "document_id": 12,
  "obligation_type": "Regulatory",
  "due_date": "2026-03-01",
  "notes": "Annual filing"
}
```

### POST `/api/compliance/obligations/{obligation_id}/complete`
Body:
```json
{"status": "Completed", "notes": "Submitted to regulator"}
```

## Dashboard - KPI Mart

### POST `/api/dashboard/kpi/rebuild-daily?for_date=2026-02-18`
Recomputes and stores daily KPI facts for tenant scope.

### GET `/api/dashboard/kpi/daily`
Query:
- `metric_code`, `date_from`, `date_to`
Response:
- `{ total, items[] }`

## Domain Events Emitted by Current Flows
- `lease.created`
- `maintenance.request.created`
- `maintenance.work_order.created`
- `invoice.created`
- `payment.received`
- `invoice.revalued`
- `document.created`
- `document.uploaded`
- `document.version_uploaded`
- `document.deleted`
- `workflow.instance.created`
- `workflow.task.completed`
