"""FastAPI application entry point."""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db, init_db, Base, engine
from app.auth.dependencies import get_current_user_from_token
from app.auth.models import UserAccount, Role
from app.auth.routes import router as auth_router
from app.modules.properties.routes import router as properties_router, tenants_router, owners_router, vendors_router
from app.modules.properties.asset_routes import router as assets_router
from app.modules.system.routes import router as system_router
from app.modules.leasing.routes import router as leasing_router
from app.modules.billing.routes import router as billing_router
from app.modules.maintenance.routes import router as maintenance_router
from app.utils.scheduler_service import scheduler
from app.dashboards.routes import router as dashboard_router
from app.modules.accounting.routes import router as accounting_router
from app.modules.crm.routes import router as crm_router
from app.modules.marketing.routes import router as marketing_router
from app.modules.compliance.routes import router as compliance_router
from app.modules.workflow.routes import router as workflow_router
from app.utils.export_service import router as export_router
from app.utils.automation_routes import router as automation_router
from app.modules.utilities.routes import router as utilities_router
from app.middleware.audit import AuditMiddleware

# Import all models so that Base.metadata knows about them
from app.modules.properties import models as _pm
from app.modules.leasing import models as _lm
from app.modules.billing import models as _bm
from app.modules.accounting import models as _am
from app.modules.maintenance import models as _mm
from app.modules.crm import models as _cm
from app.modules.marketing import models as _mkm
from app.modules.compliance import models as _cpm
from app.modules.workflow import models as _wm
from app.modules.utilities import models as _um

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Single lifespan context manager — replaces duplicate @app.on_event handlers."""
    # --- Startup ---
    Base.metadata.create_all(bind=engine)

    # Seed default roles if empty
    db = next(get_db())
    try:
        if db.query(Role).count() == 0:
            roles = [
                Role(id=1, role_name="admin", description="Full system access", is_system=True,
                     permissions={"all": True}),
                Role(id=2, role_name="manager", description="Property manager", is_system=True,
                     permissions={"properties": True, "leases": True, "billing": True, "maintenance": True}),
                Role(id=3, role_name="owner", description="Property owner portal", is_system=True,
                     permissions={"portfolio": True, "reports": True}),
                Role(id=4, role_name="tenant", description="Tenant portal", is_system=True,
                     permissions={"lease": True, "payments": True, "maintenance": True}),
                Role(id=5, role_name="vendor", description="Vendor/Maintenance portal", is_system=True,
                     permissions={"work_orders": True}),
                Role(id=6, role_name="accountant", description="Finance portal", is_system=True,
                     permissions={"billing": True, "accounting": True, "reports": True}),
            ]
            db.add_all(roles)
            db.commit()

        # Create default admin user
        from app.auth.dependencies import hash_password
        if db.query(UserAccount).filter(UserAccount.username == "admin").count() == 0:
            admin = UserAccount(
                username="admin", email="admin@propmanager.com",
                password_hash=hash_password("admin123"),
                full_name="System Administrator", role_id=1, is_active=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()

    scheduler.start()
    logger.info("Application startup complete.")

    yield

    # --- Shutdown ---
    scheduler.stop()
    logger.info("Application shutdown complete.")


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# Create directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "img"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "qrcodes"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "..", "uploads"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=os.path.join(BASE_DIR, "..", "uploads")), name="uploads")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Register Middleware
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register ALL API routers (before any route definitions)
app.include_router(auth_router)
app.include_router(properties_router)
app.include_router(system_router)
app.include_router(tenants_router)
app.include_router(owners_router)
app.include_router(vendors_router)
app.include_router(leasing_router)
app.include_router(billing_router)
app.include_router(maintenance_router)
app.include_router(dashboard_router)
app.include_router(accounting_router)
app.include_router(crm_router)
app.include_router(marketing_router)
app.include_router(compliance_router)
app.include_router(workflow_router)
app.include_router(export_router)
app.include_router(automation_router)
app.include_router(assets_router)
app.include_router(utilities_router)


# --- Health Check ---
@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


# --- Page Routes ---
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "settings": settings})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                          db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("dashboard/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/properties", response_class=HTMLResponse)
async def properties_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                           db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("properties/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/properties/{prop_id}", response_class=HTMLResponse)
async def property_detail_page(request: Request, prop_id: int,
                                user: UserAccount = Depends(get_current_user_from_token),
                                db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("properties/detail.html", {
        "request": request, "user": user, "role": role, "prop_id": prop_id, "settings": settings
    })


@app.get("/properties/{prop_id}/units/{unit_id}", response_class=HTMLResponse)
async def unit_detail_page(request: Request, prop_id: int, unit_id: int,
                            user: UserAccount = Depends(get_current_user_from_token),
                            db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("properties/unit_detail.html", {
        "request": request, "user": user, "role": role, "prop_id": prop_id, "unit_id": unit_id, "settings": settings
    })


@app.get("/assets", response_class=HTMLResponse)
async def assets_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                       db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("properties/assets.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/utilities", response_class=HTMLResponse)
async def utilities_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                          db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("utilities/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/leases", response_class=HTMLResponse)
async def leases_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                       db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("leasing/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/invoices", response_class=HTMLResponse)
async def invoices_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                         db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("billing/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                            db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("maintenance/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/tenants", response_class=HTMLResponse)
async def tenants_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                        db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("tenants/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/owners", response_class=HTMLResponse)
async def owners_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                      db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("tenants/owners.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                        db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("reports/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/accounting", response_class=HTMLResponse)
async def accounting_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                           db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("accounting/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/crm", response_class=HTMLResponse)
async def crm_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                    db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("crm/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                          db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("marketing/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/compliance", response_class=HTMLResponse)
async def compliance_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                           db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("compliance/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/workflow", response_class=HTMLResponse)
async def workflow_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                         db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return templates.TemplateResponse("workflow/index.html", {
        "request": request, "user": user, "role": role, "settings": settings
    })


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                     db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.id != 1:  # Only allow admin
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("auth/users.html", {
        "request": request, "user": user, "role": role, "settings": settings, "active_page": "users"
    })


@app.get("/roles", response_class=HTMLResponse)
async def roles_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                     db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.id != 1:  # Only allow admin
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("auth/roles.html", {
        "request": request, "user": user, "role": role, "settings": settings, "active_page": "roles"
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                         db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.id != 1:  # Only allow admin
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("system/settings.html", {
        "request": request, "user": user, "role": role, "settings": settings, "active_page": "settings"
    })


@app.get("/workflow/scheduler", response_class=HTMLResponse)
async def scheduler_page(request: Request, user: UserAccount = Depends(get_current_user_from_token),
                         db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/login")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role.id != 1:  # Only allow admin
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("workflow/scheduler.html", {
        "request": request, "user": user, "role": role, "settings": settings, "active_page": "scheduler"
    })
