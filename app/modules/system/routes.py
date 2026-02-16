"""System administration routes for settings, geo, tax, and testing."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.utils.email_service import send_email
from app.config import get_settings
from app.database import get_db
from app.modules.system.models import (
    Country, Currency, OrgSettings, TaxCode, TaxRate,
    PaymentProvider, PaymentIntent
)

router = APIRouter(
    prefix="/api/system",
    tags=["System"],
    dependencies=[Depends(require_permissions(["admin", "system"]))],
)

class EmailTestRequest(BaseModel):
    recipient: EmailStr


def _require_admin(user: UserAccount):
    if user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required")


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

@router.post("/email/test")
async def test_email(req: EmailTestRequest, user: UserAccount = Depends(get_current_user)):
    # Only allow admins to send test emails
    if user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    settings = get_settings()
    subject = f"Test Email from {settings.APP_NAME}"
    html_content = f"""
    <h2>SMTP Configuration Test</h2>
    <p>This is a test email from <strong>{settings.APP_NAME}</strong>.</p>
    <p>If you received this, your SMTP settings are working correctly!</p>
    <hr>
    <p>Server: {settings.SMTP_SERVER}:{settings.SMTP_PORT}</p>
    <p>From: {settings.SMTP_FROM_NAME} &lt;{settings.SMTP_FROM_EMAIL}&gt;</p>
    """
    
    try:
        await send_email(subject, req.recipient, html_content)
        return {"message": f"Test email sent to {req.recipient}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email failed: {str(e)}")


@router.get("/countries")
def list_countries(active_only: bool = True, db: Session = Depends(get_db),
                   user: UserAccount = Depends(get_current_user)):
    q = db.query(Country)
    if active_only:
        q = q.filter(Country.is_active == True)
    return {"total": q.count(), "items": [_dict(x) for x in q.all()]}


@router.post("/countries", status_code=201)
def create_country(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    c = Country(**{k: v for k, v in data.items() if hasattr(Country, k)})
    db.add(c)
    db.commit()
    db.refresh(c)
    return _dict(c)


@router.put("/countries/{country_id}")
def update_country(country_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    c = db.query(Country).filter(Country.id == country_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Country not found")
    for k, v in data.items():
        if hasattr(c, k) and k not in ("id",):
            setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _dict(c)


@router.get("/currencies")
def list_currencies(active_only: bool = True, db: Session = Depends(get_db),
                    user: UserAccount = Depends(get_current_user)):
    q = db.query(Currency)
    if active_only:
        q = q.filter(Currency.is_active == True)
    return {"total": q.count(), "items": [_dict(x) for x in q.all()]}


@router.post("/currencies", status_code=201)
def create_currency(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    c = Currency(**{k: v for k, v in data.items() if hasattr(Currency, k)})
    db.add(c)
    db.commit()
    db.refresh(c)
    return _dict(c)


@router.put("/currencies/{currency_id}")
def update_currency(currency_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    c = db.query(Currency).filter(Currency.id == currency_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Currency not found")
    for k, v in data.items():
        if hasattr(c, k) and k not in ("id",):
            setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _dict(c)


@router.get("/org-settings")
def get_org_settings(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    if not user.tenant_org_id:
        raise HTTPException(status_code=400, detail="User not associated with tenant org")
    settings = db.query(OrgSettings).filter(OrgSettings.tenant_org_id == user.tenant_org_id).first()
    return _dict(settings) if settings else {}


@router.post("/org-settings", status_code=201)
def upsert_org_settings(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    if not user.tenant_org_id:
        raise HTTPException(status_code=400, detail="User not associated with tenant org")
    settings = db.query(OrgSettings).filter(OrgSettings.tenant_org_id == user.tenant_org_id).first()
    if not settings:
        settings = OrgSettings(tenant_org_id=user.tenant_org_id)
        db.add(settings)
    for k, v in data.items():
        if hasattr(settings, k) and k not in ("id", "tenant_org_id"):
            setattr(settings, k, v)
    db.commit()
    db.refresh(settings)
    return _dict(settings)


@router.get("/tax-codes")
def list_tax_codes(country_code: Optional[str] = None, db: Session = Depends(get_db),
                   user: UserAccount = Depends(get_current_user)):
    q = db.query(TaxCode)
    if user.tenant_org_id:
        q = q.filter(TaxCode.tenant_org_id == user.tenant_org_id)
    if country_code:
        q = q.filter(TaxCode.country_code == country_code)
    return {"total": q.count(), "items": [_dict(x) for x in q.all()]}


@router.post("/tax-codes", status_code=201)
def create_tax_code(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    tc = TaxCode(**{k: v for k, v in data.items() if hasattr(TaxCode, k)})
    if user.tenant_org_id:
        tc.tenant_org_id = user.tenant_org_id
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return _dict(tc)


@router.put("/tax-codes/{code_id}")
def update_tax_code(code_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    tc = db.query(TaxCode).filter(TaxCode.id == code_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Tax code not found")
    for k, v in data.items():
        if hasattr(tc, k) and k not in ("id", "tenant_org_id"):
            setattr(tc, k, v)
    db.commit()
    db.refresh(tc)
    return _dict(tc)


@router.get("/tax-rates")
def list_tax_rates(code_id: Optional[int] = None, db: Session = Depends(get_db),
                   user: UserAccount = Depends(get_current_user)):
    q = db.query(TaxRate)
    if code_id:
        q = q.filter(TaxRate.tax_code_id == code_id)
    return {"total": q.count(), "items": [_dict(x) for x in q.all()]}


@router.post("/tax-rates", status_code=201)
def create_tax_rate(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    tr = TaxRate(**{k: v for k, v in data.items() if hasattr(TaxRate, k)})
    db.add(tr)
    db.commit()
    db.refresh(tr)
    return _dict(tr)


@router.put("/tax-rates/{rate_id}")
def update_tax_rate(rate_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    tr = db.query(TaxRate).filter(TaxRate.id == rate_id).first()
    if not tr:
        raise HTTPException(status_code=404, detail="Tax rate not found")
    for k, v in data.items():
        if hasattr(tr, k) and k not in ("id",):
            setattr(tr, k, v)
    db.commit()
    db.refresh(tr)
    return _dict(tr)


@router.get("/payment-providers")
def list_payment_providers(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(PaymentProvider)
    if user.tenant_org_id:
        q = q.filter(PaymentProvider.tenant_org_id == user.tenant_org_id)
    return {"total": q.count(), "items": [_dict(x) for x in q.all()]}


@router.post("/payment-providers", status_code=201)
def create_payment_provider(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    pp = PaymentProvider(**{k: v for k, v in data.items() if hasattr(PaymentProvider, k)})
    if user.tenant_org_id:
        pp.tenant_org_id = user.tenant_org_id
    db.add(pp)
    db.commit()
    db.refresh(pp)
    return _dict(pp)


@router.put("/payment-providers/{provider_id}")
def update_payment_provider(provider_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    pp = db.query(PaymentProvider).filter(PaymentProvider.id == provider_id).first()
    if not pp:
        raise HTTPException(status_code=404, detail="Provider not found")
    for k, v in data.items():
        if hasattr(pp, k) and k not in ("id", "tenant_org_id"):
            setattr(pp, k, v)
    db.commit()
    db.refresh(pp)
    return _dict(pp)


@router.post("/payment-intents", status_code=201)
def create_payment_intent(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    if not user.tenant_org_id:
        raise HTTPException(status_code=400, detail="User not associated with tenant org")
    intent = PaymentIntent(**{k: v for k, v in data.items() if hasattr(PaymentIntent, k)})
    intent.tenant_org_id = user.tenant_org_id
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return _dict(intent)


@router.get("/payment-intents")
def list_payment_intents(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(PaymentIntent)
    if user.tenant_org_id:
        q = q.filter(PaymentIntent.tenant_org_id == user.tenant_org_id)
    return {"total": q.count(), "items": [_dict(x) for x in q.all()]}
