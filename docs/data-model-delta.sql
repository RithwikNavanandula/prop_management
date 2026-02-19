-- Data model delta for architecture enhancement
-- Apply via migration tool in production. This file is a reference blueprint.

CREATE TABLE IF NOT EXISTS legal_entities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER NOT NULL,
  entity_code VARCHAR(50) NOT NULL,
  entity_name VARCHAR(200) NOT NULL,
  country_code VARCHAR(2),
  registration_number VARCHAR(100),
  tax_registration_no VARCHAR(100),
  base_currency VARCHAR(10) DEFAULT 'USD',
  timezone VARCHAR(50) DEFAULT 'UTC',
  is_active BOOLEAN DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS country_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER NOT NULL,
  country_code VARCHAR(2) NOT NULL,
  state_code VARCHAR(50),
  policy_area VARCHAR(50) NOT NULL,
  entity_type VARCHAR(50) NOT NULL,
  action_name VARCHAR(100) NOT NULL,
  priority INTEGER DEFAULT 100,
  rules_json JSON NOT NULL,
  is_active BOOLEAN DEFAULT 1,
  effective_from DATE,
  effective_to DATE,
  version_no INTEGER DEFAULT 1,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER,
  event_type VARCHAR(100) NOT NULL,
  aggregate_type VARCHAR(50) NOT NULL,
  aggregate_id INTEGER NOT NULL,
  event_key VARCHAR(200),
  payload JSON NOT NULL,
  status VARCHAR(20) DEFAULT 'Pending',
  retries INTEGER DEFAULT 0,
  available_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  published_at DATETIME,
  error_message TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fx_rate_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER NOT NULL,
  snapshot_date DATE NOT NULL,
  from_currency VARCHAR(10) NOT NULL,
  to_currency VARCHAR(10) NOT NULL,
  rate NUMERIC(18,8) NOT NULL,
  source VARCHAR(30) DEFAULT 'Manual',
  exchange_rate_daily_id INTEGER,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS multi_currency_ledger_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER NOT NULL,
  legal_entity_id INTEGER,
  reference_type VARCHAR(50) NOT NULL,
  reference_id INTEGER NOT NULL,
  posting_date DATE NOT NULL,
  txn_currency VARCHAR(10) NOT NULL,
  txn_amount NUMERIC(14,2) NOT NULL,
  base_currency VARCHAR(10) NOT NULL,
  base_amount NUMERIC(14,2) NOT NULL,
  fx_rate NUMERIC(18,8) NOT NULL,
  fx_snapshot_id INTEGER,
  entry_side VARCHAR(10) DEFAULT 'Debit',
  notes TEXT,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_instances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER,
  workflow_definition_id INTEGER NOT NULL,
  entity_type VARCHAR(50) NOT NULL,
  entity_id INTEGER NOT NULL,
  status VARCHAR(20) DEFAULT 'Running',
  current_step_no INTEGER DEFAULT 1,
  started_by INTEGER,
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  context_json JSON,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS workflow_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER,
  workflow_instance_id INTEGER NOT NULL,
  task_name VARCHAR(200) NOT NULL,
  assigned_role VARCHAR(50),
  assigned_user_id INTEGER,
  due_at DATETIME,
  status VARCHAR(20) DEFAULT 'Pending',
  decision VARCHAR(20),
  decision_notes TEXT,
  completed_by INTEGER,
  completed_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER,
  document_id INTEGER NOT NULL,
  version_number INTEGER NOT NULL,
  file_name VARCHAR(300),
  file_path VARCHAR(500),
  mime_type VARCHAR(100),
  checksum VARCHAR(128),
  notes TEXT,
  uploaded_by INTEGER,
  uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_obligations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER,
  document_id INTEGER NOT NULL,
  obligation_type VARCHAR(50) NOT NULL,
  due_date DATE NOT NULL,
  status VARCHAR(20) DEFAULT 'Open',
  assigned_to INTEGER,
  notes TEXT,
  completed_by INTEGER,
  completed_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kpi_daily_facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_org_id INTEGER NOT NULL,
  fact_date DATE NOT NULL,
  scope_type VARCHAR(30) DEFAULT 'Tenant',
  scope_id INTEGER,
  metric_code VARCHAR(100) NOT NULL,
  metric_value NUMERIC(18,4) NOT NULL,
  currency VARCHAR(10),
  dimensions JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_outbox_status ON event_outbox(status, available_at);
CREATE INDEX IF NOT EXISTS idx_event_outbox_event_type ON event_outbox(event_type);
CREATE INDEX IF NOT EXISTS idx_country_policy_lookup ON country_policies(tenant_org_id, country_code, policy_area, entity_type, action_name, priority);
CREATE INDEX IF NOT EXISTS idx_fx_snapshot_date_pair ON fx_rate_snapshots(snapshot_date, from_currency, to_currency);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_entity ON workflow_instances(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_workflow_task_instance ON workflow_tasks(workflow_instance_id, status);
CREATE INDEX IF NOT EXISTS idx_document_version_doc ON document_versions(document_id, version_number);
CREATE INDEX IF NOT EXISTS idx_document_obligation_due ON document_obligations(status, due_date);
CREATE INDEX IF NOT EXISTS idx_kpi_daily_lookup ON kpi_daily_facts(tenant_org_id, fact_date, metric_code);
