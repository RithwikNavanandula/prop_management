"""Workflow API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.modules.workflow.models import (
    WorkflowDefinition, WorkflowExecutionLog, JobSchedule, JobExecutionLog
)
from app.utils.scheduler_service import scheduler

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])

class JobCreate(BaseModel):
    job_name: str
    job_type: str = "Generic"
    schedule_type: str = "Cron"
    cron_expression: Optional[str] = None
    interval_minutes: Optional[int] = None
    daily_times: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    job_payload: Optional[Any] = None
    is_active: bool = True

class JobUpdate(BaseModel):
    job_name: Optional[str] = None
    job_type: Optional[str] = None
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_minutes: Optional[int] = None
    daily_times: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    job_payload: Optional[Any] = None
    is_active: Optional[bool] = None


# --- Definitions ---
@router.get("/definitions")
def list_workflows(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user)
):
    q = db.query(WorkflowDefinition)
    if is_active is not None:
        q = q.filter(WorkflowDefinition.is_active == is_active)
    if user.tenant_org_id:
        q = q.filter(WorkflowDefinition.tenant_org_id == user.tenant_org_id)
        
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}

@router.post("/definitions", status_code=201)
def create_workflow(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    w = WorkflowDefinition(**{k: v for k, v in data.items() if hasattr(WorkflowDefinition, k)})
    if user.tenant_org_id:
        w.tenant_org_id = user.tenant_org_id
    db.add(w)
    db.commit()
    db.refresh(w)
    return _dict(w)


# --- Logs ---
@router.get("/execution-logs")
def list_logs(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user)
):
    q = db.query(WorkflowExecutionLog)
    if status:
        q = q.filter(WorkflowExecutionLog.status == status)
    
    # Filter by workflow ownership
    if user.tenant_org_id:
        q = q.join(WorkflowDefinition).filter(WorkflowDefinition.tenant_org_id == user.tenant_org_id)
        
    items = q.order_by(WorkflowExecutionLog.triggered_at.desc()).limit(100).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


# --- Job Schedules ---
@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(JobSchedule)
    if user.tenant_org_id:
        q = q.filter(JobSchedule.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/jobs", status_code=201)
def create_job(data: JobCreate, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    j = JobSchedule(**data.model_dump(exclude_unset=True))
    if user.tenant_org_id:
        j.tenant_org_id = user.tenant_org_id
    db.add(j)
    db.commit()
    db.refresh(j)
    scheduler.add_or_update_job(j)
    return _dict(j)


@router.put("/jobs/{job_id}")
def update_job(job_id: int, data: JobUpdate, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    j = db.query(JobSchedule).filter(JobSchedule.id == job_id).first()
    if not j: raise HTTPException(404, "Job not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(j, k, v)
        
    db.commit()
    db.refresh(j)
    scheduler.add_or_update_job(j)
    return _dict(j)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    j = db.query(JobSchedule).filter(JobSchedule.id == job_id).first()
    if not j: raise HTTPException(404, "Job not found")
    # Deactivate in scheduler first
    j.is_active = False
    scheduler.add_or_update_job(j)
    db.delete(j)
    db.commit()
    return {"message": "Job deleted"}


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    j = db.query(JobSchedule).filter(JobSchedule.id == job_id).first()
    if not j: raise HTTPException(404, "Job not found")
    # Trigger manually in background
    await scheduler._execute_job_wrapper(job_id)
    return {"message": "Job triggered manually"}


@router.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(JobExecutionLog).filter(JobExecutionLog.job_id == job_id).order_by(JobExecutionLog.triggered_at.desc()).limit(50).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
