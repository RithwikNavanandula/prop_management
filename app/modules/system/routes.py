"""System administration routes for settings, geo, tax, and testing."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.utils.email_service import send_email
from app.config import get_settings
from app.database import get_db
from app.modules.system.models import (
    Country, Currency, OrgSettings, TaxCode, TaxRate,
    PaymentProvider, PaymentIntent, LegalEntity, CountryPolicy, EventOutbox
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


def _parse_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

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


@router.get("/legal-entities")
def list_legal_entities(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(LegalEntity)
    if user.tenant_org_id:
        q = q.filter(LegalEntity.tenant_org_id == user.tenant_org_id)
    return {"total": q.count(), "items": [_dict(x) for x in q.order_by(LegalEntity.id.desc()).all()]}


@router.post("/legal-entities", status_code=201)
def create_legal_entity(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    if not user.tenant_org_id:
        raise HTTPException(status_code=400, detail="User not associated with tenant org")
    item = LegalEntity(**{k: v for k, v in data.items() if hasattr(LegalEntity, k)})
    item.tenant_org_id = user.tenant_org_id
    db.add(item)
    db.commit()
    db.refresh(item)
    return _dict(item)


@router.put("/legal-entities/{entity_id}")
def update_legal_entity(entity_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    q = db.query(LegalEntity).filter(LegalEntity.id == entity_id)
    if user.tenant_org_id:
        q = q.filter(LegalEntity.tenant_org_id == user.tenant_org_id)
    item = q.first()
    if not item:
        raise HTTPException(status_code=404, detail="Legal entity not found")
    for k, v in data.items():
        if hasattr(item, k) and k not in ("id", "tenant_org_id"):
            setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return _dict(item)


@router.get("/country-policies")
def list_country_policies(
    country_code: Optional[str] = None,
    policy_area: Optional[str] = None,
    entity_type: Optional[str] = None,
    action_name: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(CountryPolicy)
    if user.tenant_org_id:
        q = q.filter(CountryPolicy.tenant_org_id == user.tenant_org_id)
    if country_code:
        q = q.filter(CountryPolicy.country_code == country_code.upper())
    if policy_area:
        q = q.filter(CountryPolicy.policy_area == policy_area)
    if entity_type:
        q = q.filter(CountryPolicy.entity_type == entity_type)
    if action_name:
        q = q.filter(CountryPolicy.action_name == action_name)
    items = q.order_by(CountryPolicy.priority.asc(), CountryPolicy.id.desc()).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/country-policies", status_code=201)
def create_country_policy(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    if not user.tenant_org_id:
        raise HTTPException(status_code=400, detail="User not associated with tenant org")
    payload = {k: v for k, v in data.items() if hasattr(CountryPolicy, k)}
    payload["effective_from"] = _parse_date(payload.get("effective_from"))
    payload["effective_to"] = _parse_date(payload.get("effective_to"))
    item = CountryPolicy(**payload)
    item.tenant_org_id = user.tenant_org_id
    item.created_by = user.id
    db.add(item)
    db.commit()
    db.refresh(item)
    return _dict(item)


@router.put("/country-policies/{policy_id}")
def update_country_policy(policy_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    q = db.query(CountryPolicy).filter(CountryPolicy.id == policy_id)
    if user.tenant_org_id:
        q = q.filter(CountryPolicy.tenant_org_id == user.tenant_org_id)
    item = q.first()
    if not item:
        raise HTTPException(status_code=404, detail="Country policy not found")
    for k, v in data.items():
        if hasattr(item, k) and k not in ("id", "tenant_org_id", "created_at"):
            if k in ("effective_from", "effective_to"):
                setattr(item, k, _parse_date(v))
            else:
                setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return _dict(item)


@router.post("/country-policies/resolve")
def resolve_country_policy(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    """Resolve the most specific active policy for an action in a country/state context."""
    if not user.tenant_org_id:
        raise HTTPException(status_code=400, detail="User not associated with tenant org")
    country_code = str(data.get("country_code", "")).upper()
    state_code = data.get("state_code")
    policy_area = data.get("policy_area")
    entity_type = data.get("entity_type")
    action_name = data.get("action_name")
    effective_on = _parse_date(data.get("effective_on")) or date.today()
    if not all([country_code, policy_area, entity_type, action_name]):
        raise HTTPException(status_code=400, detail="country_code, policy_area, entity_type, action_name are required")

    q = db.query(CountryPolicy).filter(
        CountryPolicy.tenant_org_id == user.tenant_org_id,
        CountryPolicy.country_code == country_code,
        CountryPolicy.policy_area == policy_area,
        CountryPolicy.entity_type == entity_type,
        CountryPolicy.action_name == action_name,
        CountryPolicy.is_active == True,
    )
    items = q.order_by(CountryPolicy.priority.asc(), CountryPolicy.id.desc()).all()

    valid = []
    for p in items:
        if p.effective_from and p.effective_from > effective_on:
            continue
        if p.effective_to and p.effective_to < effective_on:
            continue
        if state_code and p.state_code and p.state_code != state_code:
            continue
        valid.append(p)

    if not valid:
        return {"matched": False, "policy": None}

    state_specific = [p for p in valid if p.state_code and state_code and p.state_code == state_code]
    chosen = (state_specific or valid)[0]
    return {"matched": True, "policy": _dict(chosen)}


@router.get("/event-outbox")
def list_event_outbox(
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    _require_admin(user)
    q = db.query(EventOutbox)
    if user.tenant_org_id:
        q = q.filter(EventOutbox.tenant_org_id == user.tenant_org_id)
    if status:
        q = q.filter(EventOutbox.status == status)
    if event_type:
        q = q.filter(EventOutbox.event_type == event_type)
    items = q.order_by(EventOutbox.id.desc()).limit(max(1, min(limit, 1000))).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/event-outbox/{event_id}/mark-published")
def mark_event_published(event_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    _require_admin(user)
    q = db.query(EventOutbox).filter(EventOutbox.id == event_id)
    if user.tenant_org_id:
        q = q.filter(EventOutbox.tenant_org_id == user.tenant_org_id)
    evt = q.first()
    if not evt:
        raise HTTPException(status_code=404, detail="Event not found")
    evt.status = "Published"
    from datetime import datetime
    evt.published_at = datetime.utcnow()
    db.commit()
    db.refresh(evt)
    return _dict(evt)
