"""Automated test suite for Property Management V2."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_URL"] = "sqlite:///./test_prop_management.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base

TEST_DB = "sqlite:///./test_prop_management.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# Store token globally for reuse
_token = None


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_prop_management.db"):
        os.remove("./test_prop_management.db")


def _login():
    """Register + login to get auth token."""
    global _token
    if _token:
        return {"Authorization": f"Bearer {_token}"}

    # Register
    client.post("/api/auth/register", json={
        "username": "testadmin", "email": "test@example.com",
        "password": "Test1234!", "full_name": "Test Admin"
    })

    # Login (JSON body, not form data)
    r = client.post("/api/auth/login", json={
        "username": "testadmin", "password": "Test1234!"
    })
    if r.status_code == 200:
        _token = r.json().get("access_token", "")
    return {"Authorization": f"Bearer {_token}"}


# ═══════════════════════════════════════
# Health
# ═══════════════════════════════════════
class TestHealth:
    def test_health_endpoint(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


# ═══════════════════════════════════════
# Auth Flow
# ═══════════════════════════════════════
class TestAuth:
    def test_register_user(self):
        r = client.post("/api/auth/register", json={
            "username": "testuser2", "email": "test2@example.com",
            "password": "Test1234!", "full_name": "Test User 2"
        })
        assert r.status_code in (200, 201), r.text

    def test_login(self):
        r = client.post("/api/auth/login", json={
            "username": "testuser2", "password": "Test1234!"
        })
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()

    def test_login_wrong_password(self):
        r = client.post("/api/auth/login", json={
            "username": "testuser2", "password": "wrongpass"
        })
        assert r.status_code == 401


# ═══════════════════════════════════════
# Properties CRUD
# ═══════════════════════════════════════
class TestProperties:
    def test_list_properties(self):
        r = client.get("/api/properties", headers=_login())
        assert r.status_code == 200

    def test_create_property(self):
        r = client.post("/api/properties", json={
            "property_name": "Test Property", "property_code": "TP-001",
            "property_type": "Residential", "status": "Active"
        }, headers=_login())
        assert r.status_code in (200, 201), r.text

    def test_list_tenants(self):
        r = client.get("/api/tenants", headers=_login())
        assert r.status_code == 200

    def test_create_tenant(self):
        r = client.post("/api/tenants", json={
            "first_name": "Test", "last_name": "Tenant",
            "tenant_code": "TT-001", "email": "test.tenant@test.com"
        }, headers=_login())
        assert r.status_code in (200, 201)

    def test_list_owners(self):
        r = client.get("/api/owners", headers=_login())
        assert r.status_code == 200

    def test_list_vendors(self):
        r = client.get("/api/vendors", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# Billing
# ═══════════════════════════════════════
class TestBilling:
    def test_list_invoices(self):
        r = client.get("/api/billing/invoices", headers=_login())
        assert r.status_code == 200

    def test_list_payments(self):
        r = client.get("/api/billing/payments", headers=_login())
        assert r.status_code == 200

    def test_list_late_fee_rules(self):
        r = client.get("/api/billing/late-fee-rules", headers=_login())
        assert r.status_code == 200

    def test_list_payment_methods(self):
        r = client.get("/api/billing/payment-methods", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# Leasing (correct URL: /api/leases)
# ═══════════════════════════════════════
class TestLeasing:
    def test_list_leases(self):
        r = client.get("/api/leases", headers=_login())
        assert r.status_code == 200

    def test_get_lease_not_found(self):
        r = client.get("/api/leases/99999", headers=_login())
        assert r.status_code == 404


# ═══════════════════════════════════════
# Maintenance
# ═══════════════════════════════════════
class TestMaintenance:
    def test_list_requests(self):
        r = client.get("/api/maintenance/requests", headers=_login())
        assert r.status_code == 200

    def test_list_work_orders(self):
        r = client.get("/api/maintenance/work-orders", headers=_login())
        assert r.status_code == 200

    def test_list_sla_rules(self):
        r = client.get("/api/maintenance/sla-rules", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# Accounting
# ═══════════════════════════════════════
class TestAccounting:
    def test_list_accounts(self):
        r = client.get("/api/accounting/chart-of-accounts", headers=_login())
        assert r.status_code == 200

    def test_list_journal_entries(self):
        r = client.get("/api/accounting/journal-entries", headers=_login())
        assert r.status_code == 200

    def test_balance_sheet(self):
        r = client.get("/api/accounting/reports/balance-sheet?as_of=2026-02-13", headers=_login())
        assert r.status_code == 200

    def test_income_statement(self):
        r = client.get("/api/accounting/reports/income-statement?start_date=2026-01-01&end_date=2026-02-13", headers=_login())
        assert r.status_code == 200

    def test_trial_balance(self):
        r = client.get("/api/accounting/reports/trial-balance?as_of=2026-02-13", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# Dashboards (correct URL: /api/dashboard/*)
# ═══════════════════════════════════════
class TestDashboards:
    def test_portfolio_dashboard(self):
        r = client.get("/api/dashboard/portfolio", headers=_login())
        assert r.status_code == 200

    def test_finance_dashboard(self):
        r = client.get("/api/dashboard/finance", headers=_login())
        assert r.status_code == 200

    def test_maintenance_dashboard(self):
        r = client.get("/api/dashboard/maintenance", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# CRM
# ═══════════════════════════════════════
class TestCRM:
    def test_list_contacts(self):
        r = client.get("/api/crm/contacts", headers=_login())
        assert r.status_code == 200

    def test_list_threads(self):
        r = client.get("/api/crm/threads", headers=_login())
        assert r.status_code == 200

    def test_list_tasks(self):
        r = client.get("/api/crm/tasks", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# Marketing
# ═══════════════════════════════════════
class TestMarketing:
    def test_list_listings(self):
        r = client.get("/api/marketing/listings", headers=_login())
        assert r.status_code == 200

    def test_list_leads(self):
        r = client.get("/api/marketing/leads", headers=_login())
        assert r.status_code == 200

    def test_list_applications(self):
        r = client.get("/api/marketing/applications", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# Compliance
# ═══════════════════════════════════════
class TestCompliance:
    def test_list_requirements(self):
        r = client.get("/api/compliance/requirements", headers=_login())
        assert r.status_code == 200

    def test_list_documents(self):
        r = client.get("/api/compliance/documents", headers=_login())
        assert r.status_code == 200

    def test_list_inspections(self):
        r = client.get("/api/compliance/inspections", headers=_login())
        assert r.status_code == 200

    def test_list_document_types(self):
        r = client.get("/api/compliance/document-types", headers=_login())
        assert r.status_code == 200


# ═══════════════════════════════════════
# Export + Automation
# ═══════════════════════════════════════
class TestExportAutomation:
    def test_export_properties(self):
        r = client.get("/api/export/properties", headers=_login())
        assert r.status_code == 200

    def test_expiring_leases(self):
        r = client.get("/api/automation/expiring-leases", headers=_login())
        assert r.status_code == 200

    def test_generate_invoices(self):
        r = client.post("/api/automation/generate-invoices", headers=_login())
        assert r.status_code == 200

    def test_auto_terminate(self):
        r = client.post("/api/automation/auto-terminate", headers=_login())
        assert r.status_code == 200
