"""CRM API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.modules.crm.models import (
    Contact, CommunicationThread, Message, Task
)

router = APIRouter(prefix="/api/crm", tags=["CRM"])


# --- Contacts ---
@router.get("/contacts")
def list_contacts(
    search: Optional[str] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user)
):
    q = db.query(Contact).filter(Contact.status == "Active")
    if type:
        q = q.filter(Contact.contact_type == type)
    if search:
        q = q.filter(or_(
            Contact.first_name.ilike(f"%{search}%"),
            Contact.last_name.ilike(f"%{search}%"),
            Contact.email.ilike(f"%{search}%")
        ))
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}

@router.post("/contacts", status_code=201)
def create_contact(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    c = Contact(**{k: v for k, v in data.items() if hasattr(Contact, k)})
    if user.tenant_org_id:
        c.tenant_org_id = user.tenant_org_id
    db.add(c)
    db.commit()
    db.refresh(c)
    return _dict(c)


# --- Threads ---
@router.get("/threads")
def list_threads(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user)
):
    q = db.query(CommunicationThread)
    if status:
        q = q.filter(CommunicationThread.status == status)
    
    # Filter threads where user is participant or has access (simplified for now: all tenant threads)
    if user.tenant_org_id:
        q = q.filter(CommunicationThread.tenant_org_id == user.tenant_org_id)
        
    items = q.order_by(CommunicationThread.updated_at.desc() if hasattr(CommunicationThread, 'updated_at') else CommunicationThread.created_at.desc()).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}

@router.post("/threads", status_code=201)
def create_thread(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    t = CommunicationThread(**{k: v for k, v in data.items() if hasattr(CommunicationThread, k)})
    if user.tenant_org_id:
        t.tenant_org_id = user.tenant_org_id
    db.add(t)
    db.commit()
    db.refresh(t)
    return _dict(t)


# --- Messages ---
@router.get("/threads/{thread_id}/messages")
def list_messages(thread_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.sent_at).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}

@router.post("/threads/{thread_id}/messages", status_code=201)
def add_message(thread_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    thread = db.query(CommunicationThread).filter(CommunicationThread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")
        
    msg = Message(**{k: v for k, v in data.items() if hasattr(Message, k)})
    msg.thread_id = thread_id
    msg.sender_type = "User" # Simplified
    msg.sender_id = user.id
    
    db.add(msg)
    # Update thread status/timestamp if fields existed
    db.commit()
    db.refresh(msg)
    return _dict(msg)


# --- Tasks ---
@router.get("/tasks")
def list_tasks(
    status: Optional[str] = None,
    assigned_to_me: bool = False,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user)
):
    q = db.query(Task)
    if status:
        q = q.filter(Task.status == status)
    if assigned_to_me:
        q = q.filter(Task.assigned_to == user.id)
    elif user.tenant_org_id:
         q = q.filter(Task.tenant_org_id == user.tenant_org_id)
         
    items = q.order_by(Task.due_date).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}

@router.post("/tasks", status_code=201)
def create_task(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    t = Task(**{k: v for k, v in data.items() if hasattr(Task, k)})
    if user.tenant_org_id:
        t.tenant_org_id = user.tenant_org_id
    if "assigned_to" not in data:
        t.assigned_to = user.id
    db.add(t)
    db.commit()
    db.refresh(t)
    return _dict(t)


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
