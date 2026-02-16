"""Job Scheduler service using APScheduler."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, time
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.modules.workflow.models import JobSchedule, JobExecutionLog
from typing import Dict, Any

logger = logging.getLogger(__name__)

class JobScheduler:
    _instance = None
    _scheduler = AsyncIOScheduler()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobScheduler, cls).__new__(cls)
        return cls._instance

    @classmethod
    def start(cls):
        if not cls._scheduler.running:
            cls._scheduler.start()
            logger.info("APScheduler started.")
            cls.load_all_jobs()

    @classmethod
    def stop(cls):
        if cls._scheduler.running:
            cls._scheduler.shutdown()
            logger.info("APScheduler stopped.")

    @classmethod
    def load_all_jobs(cls):
        """Load all active jobs from the database into the scheduler."""
        db = SessionLocal()
        try:
            jobs = db.query(JobSchedule).filter(JobSchedule.is_active == True).all()
            for job in jobs:
                cls.add_or_update_job(job)
            logger.info(f"Loaded {len(jobs)} jobs into scheduler.")
        finally:
            db.close()

    @classmethod
    def add_or_update_job(cls, job: JobSchedule):
        """Register or update a job in the APScheduler."""
        job_id = f"job_{job.id}"
        
        # Remove existing job if any
        if cls._scheduler.get_job(job_id):
            cls._scheduler.remove_job(job_id)

        if not job.is_active:
            return

        trigger = cls._get_trigger(job)
        if trigger:
            cls._scheduler.add_job(
                cls._execute_job_wrapper,
                trigger,
                id=job_id,
                args=[job.id],
                replace_existing=True,
                misfire_grace_time=300
            )
            logger.info(f"Scheduled job: {job.job_name} (ID: {job.id}) with type {job.schedule_type}")

    @staticmethod
    def _get_trigger(job: JobSchedule):
        """Construct the appropriate APScheduler trigger based on JobSchedule config."""
        try:
            if job.schedule_type == "Cron" and job.cron_expression:
                return CronTrigger.from_crontab(job.cron_expression)
            
            if job.schedule_type == "Interval" and job.interval_minutes:
                return IntervalTrigger(minutes=job.interval_minutes, start_date=job.start_date, end_date=job.end_date)
            
            if job.schedule_type == "Once" and job.start_date:
                return DateTrigger(run_date=job.start_date)
            
            if job.schedule_type == "DailyMulti" and job.daily_times:
                # Daily multi requires multiple triggers or a custom trigger.
                # Here we implement it as multiple cron-like triggers by joining them.
                # However, for simplicity in APScheduler, we often add multiple jobs or a custom combining trigger.
                # Refined approach: use cron for each specific time.
                times = job.daily_times if isinstance(job.daily_times, list) else []
                # APScheduler doesn't easily support 'OR' triggers in one go without 'AndTrigger/OrTrigger'
                # Simplified: use Cron with specific hours/minutes if possible, or multi-job.
                # For "Max Options", we'll use a string of hours/minutes for Cron.
                hrs = []
                mins = []
                for t_str in times:
                    try:
                        h, m = t_str.split(':')
                        hrs.append(h)
                        mins.append(m)
                    except: continue
                if hrs:
                    return CronTrigger(hour=",".join(set(hrs)), minute=",".join(set(mins)), start_date=job.start_date, end_date=job.end_date)
            
        except Exception as e:
            logger.error(f"Error creating trigger for job {job.id}: {e}")
        return None

    @staticmethod
    async def _execute_job_wrapper(job_id: int):
        """Wrapper to handle database session and logging for job execution."""
        db = SessionLocal()
        job = db.query(JobSchedule).filter(JobSchedule.id == job_id).first()
        if not job:
            db.close()
            return

        logger.info(f"Executing job: {job.job_name}")
        log = JobExecutionLog(job_id=job.id, status="Running")
        db.add(log)
        db.commit()

        try:
            # Update last_run_at early
            job.last_run_at = datetime.now()
            db.commit()
            
            # Placeholder for actual job logic
            # await cls._perform_job_action(job)
            
            log.status = "Completed"
            log.completed_at = datetime.now()
            db.commit()
            logger.info(f"Job {job.job_name} finished successfully.")
        except Exception as e:
            log.status = "Failed"
            log.error_message = str(e)
            log.completed_at = datetime.now()
            db.commit()
            logger.error(f"Job {job.job_name} failed: {e}")
        finally:
            db.close()

scheduler = JobScheduler()
