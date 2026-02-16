"""System administration routes for settings and testing."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.utils.email_service import send_email
from app.config import get_settings

router = APIRouter(prefix="/api/system", tags=["System"])

class EmailTestRequest(BaseModel):
    recipient: EmailStr

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
