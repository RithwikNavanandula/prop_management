"""Workflow API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.workflow.models import (
    WorkflowDefinition, WorkflowExecutionLog, JobSchedule, JobExecutionLog,
    WorkflowInstance, WorkflowTask
)
from app.utils.scheduler_service import scheduler
from app.utils.event_service import emit_outbox_event

router = APIRouter(
    prefix="/api/workflow",
    tags=["Workflow"],
    dependencies=[Depends(require_permissions(["workflow", "automation"]))],
)

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


def _workflow_query_for_user(db: Session, user: UserAccount):
    q = db.query(WorkflowDefinition)
    if user.tenant_org_id:
        q = q.filter(WorkflowDefinition.tenant_org_id == user.tenant_org_id)
    return q


def _sanitize_workflow_data(data: dict) -> dict:
    clean = {}
    for k, v in data.items():
        if not hasattr(WorkflowDefinition, k) or k in ("id", "created_at", "updated_at", "tenant_org_id"):
            continue
        if k == "is_active" and not isinstance(v, bool):
            clean[k] = str(v).lower() in ("1", "true", "yes", "on")
        else:
            clean[k] = v
    return clean


def _instance_query_for_user(db: Session, user: UserAccount):
    q = db.query(WorkflowInstance)
    if user.tenant_org_id:
        q = q.filter(WorkflowInstance.tenant_org_id == user.tenant_org_id)
    return q


# --- Definitions ---
@router.get("/definitions")
def list_workflows(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user)
):
    q = _workflow_query_for_user(db, user)
    if is_active is not None:
        q = q.filter(WorkflowDefinition.is_active == is_active)
        
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}

@router.post("/definitions", status_code=201)
def create_workflow(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    clean = _sanitize_workflow_data(data)
    if not clean.get("workflow_name"):
        raise HTTPException(400, "Field 'workflow_name' is required")
    w = WorkflowDefinition(**clean)
    if user.tenant_org_id:
        w.tenant_org_id = user.tenant_org_id
    db.add(w)
    db.commit()
    db.refresh(w)
    return _dict(w)


@router.get("/definitions/{workflow_id}")
def get_workflow(workflow_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    w = _workflow_query_for_user(db, user).filter(WorkflowDefinition.id == workflow_id).first()
    if not w:
        raise HTTPException(404, "Workflow not found")
    return _dict(w)


@router.put("/definitions/{workflow_id}")
def update_workflow(workflow_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    w = _workflow_query_for_user(db, user).filter(WorkflowDefinition.id == workflow_id).first()
    if not w:
        raise HTTPException(404, "Workflow not found")
    clean = _sanitize_workflow_data(data)
    for k, v in clean.items():
        setattr(w, k, v)
    if not w.workflow_name:
        raise HTTPException(400, "Field 'workflow_name' is required")
    db.commit()
    db.refresh(w)
    return _dict(w)


@router.delete("/definitions/{workflow_id}")
def delete_workflow(workflow_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    w = _workflow_query_for_user(db, user).filter(WorkflowDefinition.id == workflow_id).first()
    if not w:
        raise HTTPException(404, "Workflow not found")
    db.delete(w)
    db.commit()
    return {"message": "Workflow deleted"}


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


@router.get("/instances")
def list_instances(
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = _instance_query_for_user(db, user)
    if status:
        q = q.filter(WorkflowInstance.status == status)
    if entity_type:
        q = q.filter(WorkflowInstance.entity_type == entity_type)
    if entity_id:
        q = q.filter(WorkflowInstance.entity_id == entity_id)
    items = q.order_by(WorkflowInstance.id.desc()).limit(500).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/instances", status_code=201)
def create_instance(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    workflow_definition_id = data.get("workflow_definition_id")
    entity_type = data.get("entity_type")
    entity_id = data.get("entity_id")
    if not workflow_definition_id or not entity_type or entity_id in (None, ""):
        raise HTTPException(400, "workflow_definition_id, entity_type, entity_id are required")

    wf_q = _workflow_query_for_user(db, user).filter(WorkflowDefinition.id == int(workflow_definition_id))
    wf = wf_q.first()
    if not wf:
        raise HTTPException(404, "Workflow definition not found")

    inst = WorkflowInstance(
        tenant_org_id=user.tenant_org_id,
        workflow_definition_id=wf.id,
        entity_type=str(entity_type),
        entity_id=int(entity_id),
        status=data.get("status", "Running"),
        current_step_no=int(data.get("current_step_no", 1)),
        started_by=user.id,
        context_json=data.get("context_json"),
    )
    db.add(inst)
    db.flush()

    first_task_name = data.get("first_task_name") or f"{wf.workflow_name} Approval"
    if data.get("create_initial_task", True):
        db.add(WorkflowTask(
            tenant_org_id=user.tenant_org_id,
            workflow_instance_id=inst.id,
            task_name=first_task_name,
            assigned_role=data.get("assigned_role"),
            assigned_user_id=data.get("assigned_user_id"),
            status="Pending",
        ))
    emit_outbox_event(
        db=db,
        tenant_org_id=user.tenant_org_id,
        event_type="workflow.instance.created",
        aggregate_type="WorkflowInstance",
        aggregate_id=inst.id,
        payload={"workflow_definition_id": wf.id, "entity_type": inst.entity_type, "entity_id": inst.entity_id},
        event_key=f"workflow.instance.created.{inst.id}",
    )
    db.commit()
    db.refresh(inst)
    return _dict(inst)


@router.get("/instances/{instance_id}")
def get_instance(instance_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inst = _instance_query_for_user(db, user).filter(WorkflowInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(404, "Workflow instance not found")
    d = _dict(inst)
    tasks = db.query(WorkflowTask).filter(WorkflowTask.workflow_instance_id == inst.id).order_by(WorkflowTask.id.asc()).all()
    d["tasks"] = [_dict(t) for t in tasks]
    return d


@router.get("/instances/{instance_id}/tasks")
def list_instance_tasks(instance_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inst = _instance_query_for_user(db, user).filter(WorkflowInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(404, "Workflow instance not found")
    items = db.query(WorkflowTask).filter(WorkflowTask.workflow_instance_id == instance_id).order_by(WorkflowTask.id.asc()).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/instances/{instance_id}/tasks", status_code=201)
def create_instance_task(instance_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inst = _instance_query_for_user(db, user).filter(WorkflowInstance.id == instance_id).first()
    if not inst:
        raise HTTPException(404, "Workflow instance not found")
    if not data.get("task_name"):
        raise HTTPException(400, "task_name is required")
    task = WorkflowTask(
        tenant_org_id=user.tenant_org_id,
        workflow_instance_id=instance_id,
        task_name=data["task_name"],
        assigned_role=data.get("assigned_role"),
        assigned_user_id=data.get("assigned_user_id"),
        status=data.get("status", "Pending"),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _dict(task)


@router.put("/tasks/{task_id}")
def update_task(task_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(WorkflowTask).filter(WorkflowTask.id == task_id)
    if user.tenant_org_id:
        q = q.filter(WorkflowTask.tenant_org_id == user.tenant_org_id)
    task = q.first()
    if not task:
        raise HTTPException(404, "Workflow task not found")
    for k, v in data.items():
        if hasattr(task, k) and k not in ("id", "tenant_org_id", "workflow_instance_id", "created_at"):
            setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return _dict(task)


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(WorkflowTask).filter(WorkflowTask.id == task_id)
    if user.tenant_org_id:
        q = q.filter(WorkflowTask.tenant_org_id == user.tenant_org_id)
    task = q.first()
    if not task:
        raise HTTPException(404, "Workflow task not found")
    decision = data.get("decision", "Completed")
    task.status = "Completed"
    task.decision = decision
    task.decision_notes = data.get("decision_notes")
    task.completed_by = user.id
    task.completed_at = datetime.utcnow()

    inst = _instance_query_for_user(db, user).filter(WorkflowInstance.id == task.workflow_instance_id).first()
    if inst:
        open_tasks = db.query(WorkflowTask).filter(
            WorkflowTask.workflow_instance_id == inst.id,
            WorkflowTask.status.in_(["Pending", "InProgress"])
        ).count()
        if open_tasks == 0:
            inst.status = "Completed"
            inst.completed_at = datetime.utcnow()
    emit_outbox_event(
        db=db,
        tenant_org_id=user.tenant_org_id,
        event_type="workflow.task.completed",
        aggregate_type="WorkflowTask",
        aggregate_id=task.id,
        payload={"workflow_instance_id": task.workflow_instance_id, "decision": decision},
        event_key=f"workflow.task.completed.{task.id}",
    )
    db.commit()
    db.refresh(task)
    return _dict(task)


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
    q = db.query(JobSchedule).filter(JobSchedule.id == job_id)
    if user.tenant_org_id:
        q = q.filter(JobSchedule.tenant_org_id == user.tenant_org_id)
    j = q.first()
    if not j:
        raise HTTPException(404, "Job not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(j, k, v)
        
    db.commit()
    db.refresh(j)
    scheduler.add_or_update_job(j)
    return _dict(j)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(JobSchedule).filter(JobSchedule.id == job_id)
    if user.tenant_org_id:
        q = q.filter(JobSchedule.tenant_org_id == user.tenant_org_id)
    j = q.first()
    if not j:
        raise HTTPException(404, "Job not found")
    # Deactivate in scheduler first
    j.is_active = False
    scheduler.add_or_update_job(j)
    db.delete(j)
    db.commit()
    return {"message": "Job deleted"}


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(JobSchedule).filter(JobSchedule.id == job_id)
    if user.tenant_org_id:
        q = q.filter(JobSchedule.tenant_org_id == user.tenant_org_id)
    j = q.first()
    if not j:
        raise HTTPException(404, "Job not found")
    # Trigger manually in background
    await scheduler._execute_job_wrapper(job_id)
    return {"message": "Job triggered manually"}


@router.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(JobExecutionLog).filter(JobExecutionLog.job_id == job_id)
    if user.tenant_org_id:
        q = q.join(JobSchedule, JobExecutionLog.job_id == JobSchedule.id).filter(JobSchedule.tenant_org_id == user.tenant_org_id)
    items = q.order_by(JobExecutionLog.triggered_at.desc()).limit(50).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
