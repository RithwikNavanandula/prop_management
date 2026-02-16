"""Workflow models – Definition, Step, Trigger, Action, ExecutionLog."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    workflow_name = Column(String(200), nullable=False)
    trigger_event = Column(String(100))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definitions.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    step_name = Column(String(200), nullable=False)
    action_type = Column(String(50))
    action_config = Column(JSON)
    condition_expression = Column(Text)
    delay_minutes = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class WorkflowTrigger(Base):
    __tablename__ = "workflow_triggers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definitions.id"), nullable=False)
    trigger_type = Column(String(20), default="Event")
    event_name = Column(String(100))
    schedule_cron = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class WorkflowAction(Base):
    __tablename__ = "workflow_actions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    step_id = Column(Integer, ForeignKey("workflow_steps.id"), nullable=False)
    action_type = Column(String(50))
    target_entity = Column(String(50))
    parameters = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())


class WorkflowExecutionLog(Base):
    __tablename__ = "workflow_execution_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflow_definitions.id"), nullable=False)
    triggered_by = Column(String(100))
    triggered_at = Column(DateTime, server_default=func.now())
    status = Column(String(20), default="Running")
    completed_at = Column(DateTime)
    error_message = Column(Text)


class JobSchedule(Base):
    __tablename__ = "job_schedules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    job_name = Column(String(200), nullable=False)
    job_type = Column(String(50), default="Generic")  # e.g., Email, Report, Billing
    
    # Schedule Configuration
    schedule_type = Column(String(20), default="Cron")  # Cron, Interval, Once, DailyMulti
    cron_expression = Column(String(100))  # standard cron format
    interval_minutes = Column(Integer)
    daily_times = Column(JSON)  # List of strings ["09:00", "14:00", "21:00"]
    
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Payload & State
    job_payload = Column(JSON)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class JobExecutionLog(Base):
    __tablename__ = "job_execution_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("job_schedules.id"), nullable=False)
    triggered_at = Column(DateTime, server_default=func.now())
    status = Column(String(20), default="Running")  # Running, Completed, Failed
    completed_at = Column(DateTime)
    error_message = Column(Text)
