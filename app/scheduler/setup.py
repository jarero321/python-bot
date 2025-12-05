"""Configuración del scheduler con APScheduler."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Scheduler global
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Obtiene la instancia del scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            timezone=settings.tz,
            job_defaults={
                "coalesce": True,  # Combinar ejecuciones perdidas
                "max_instances": 1,  # Una sola instancia por job
                "misfire_grace_time": 60,  # Gracia de 60 segundos
            },
        )
    return _scheduler


async def setup_scheduler() -> AsyncIOScheduler:
    """Configura y arranca el scheduler con todos los jobs."""
    scheduler = get_scheduler()

    # Importar jobs
    from app.scheduler.jobs.morning_briefing import morning_briefing_job, monday_workload_alert
    from app.scheduler.jobs.hourly_checkin import hourly_checkin_job
    from app.scheduler.jobs.gym_reminder import gym_reminder_job
    from app.scheduler.jobs.nutrition_reminder import nutrition_reminder_job
    from app.scheduler.jobs.persistent_reminders import check_persistent_reminders_job
    from app.scheduler.jobs.weekly_review import weekly_review_job
    from app.scheduler.jobs.payday_alert import pre_payday_job, post_payday_job
    from app.scheduler.jobs.study_reminder import study_reminder_job
    from app.scheduler.jobs.proactive_tracker import (
        proactive_task_check,
        deadline_alert_check,
        stale_tasks_check,
        task_completion_follow_up,
        blocked_tasks_reminder,
    )
    from app.scheduler.jobs.reminder_dispatcher import (
        dispatch_pending_reminders,
        cleanup_old_reminders,
        send_evening_planning_prompt,
        send_morning_plan_reminder,
    )
    from app.scheduler.jobs.rag_sync import (
        sync_rag_index_job,
        cleanup_stale_rag_entries_job,
    )
    from app.scheduler.jobs.interaction_follow_up import (
        check_pending_interactions_job,
        cleanup_interactions_job,
    )
    from app.scheduler.jobs.metrics_sync import (
        send_daily_metrics_summary,
        send_performance_alert,
    )
    from app.scheduler.jobs.sync_job import (
        run_full_sync,
        sync_tasks_only,
    )
    from app.scheduler.jobs.jira_reminder import jira_reminder_job

    # ==================== MORNING BRIEFING ====================
    # 6:30 AM todos los días
    scheduler.add_job(
        morning_briefing_job,
        CronTrigger(hour=6, minute=30),
        id="morning_briefing",
        name="Morning Briefing",
        replace_existing=True,
    )
    logger.info("Job configurado: Morning Briefing (6:30 AM)")

    # ==================== HOURLY CHECK-IN ====================
    # Cada hora de 9 AM a 6 PM, lunes a viernes
    scheduler.add_job(
        hourly_checkin_job,
        CronTrigger(hour="9-18", minute=30, day_of_week="mon-fri"),
        id="hourly_checkin",
        name="Hourly Check-in",
        replace_existing=True,
    )
    logger.info("Job configurado: Hourly Check-in (9:30-18:30 L-V)")

    # ==================== GYM REMINDERS ====================
    # 7:15, 7:30, 7:45 AM lunes a viernes
    for minute, level in [(15, "gentle"), (30, "normal"), (45, "insistent")]:
        scheduler.add_job(
            gym_reminder_job,
            CronTrigger(hour=7, minute=minute, day_of_week="mon-fri"),
            id=f"gym_reminder_{level}",
            name=f"Gym Reminder ({level})",
            kwargs={"escalation_level": level},
            replace_existing=True,
        )
    logger.info("Jobs configurados: Gym Reminders (7:15, 7:30, 7:45 L-V)")

    # ==================== NUTRITION REMINDER ====================
    # 9:00 PM todos los días
    scheduler.add_job(
        nutrition_reminder_job,
        CronTrigger(hour=21, minute=0),
        id="nutrition_reminder",
        name="Nutrition Reminder",
        replace_existing=True,
    )
    logger.info("Job configurado: Nutrition Reminder (9:00 PM)")

    # ==================== PERSISTENT REMINDERS CHECK ====================
    # Cada 30 minutos
    scheduler.add_job(
        check_persistent_reminders_job,
        IntervalTrigger(minutes=30),
        id="persistent_reminders",
        name="Persistent Reminders Check",
        replace_existing=True,
    )
    logger.info("Job configurado: Persistent Reminders (cada 30 min)")

    # ==================== WEEKLY REVIEW ====================
    # Domingos a las 10:00 AM
    scheduler.add_job(
        weekly_review_job,
        CronTrigger(hour=10, minute=0, day_of_week="sun"),
        id="weekly_review",
        name="Weekly Review",
        replace_existing=True,
    )
    logger.info("Job configurado: Weekly Review (Domingo 10:00 AM)")

    # ==================== STUDY REMINDER ====================
    # 5:30 PM todos los días
    scheduler.add_job(
        study_reminder_job,
        CronTrigger(hour=17, minute=30),
        id="study_reminder",
        name="Study Reminder",
        replace_existing=True,
    )
    logger.info("Job configurado: Study Reminder (5:30 PM)")

    # ==================== PAYDAY ALERTS ====================
    # Pre-quincena: días 13 y 28
    scheduler.add_job(
        pre_payday_job,
        CronTrigger(hour=9, minute=0, day="13,28"),
        id="pre_payday",
        name="Pre-Payday Alert",
        replace_existing=True,
    )
    logger.info("Job configurado: Pre-Payday Alert (días 13, 28 a las 9:00 AM)")

    # Post-quincena: días 15 y último día del mes (30)
    scheduler.add_job(
        post_payday_job,
        CronTrigger(hour=18, minute=0, day="15,30"),
        id="post_payday",
        name="Post-Payday Reminder",
        replace_existing=True,
    )
    logger.info("Job configurado: Post-Payday Reminder (días 15, 30 a las 6:00 PM)")

    # ==================== MONDAY WORKLOAD ALERT ====================
    # Lunes a las 7:00 AM - resumen de carga de trabajo
    scheduler.add_job(
        monday_workload_alert,
        CronTrigger(hour=7, minute=0, day_of_week="mon"),
        id="monday_workload",
        name="Monday Workload Alert",
        replace_existing=True,
    )
    logger.info("Job configurado: Monday Workload Alert (Lunes 7:00 AM)")

    # ==================== PROACTIVE TASK TRACKING ====================

    # Verificación proactiva cada hora (9-18 L-V)
    scheduler.add_job(
        proactive_task_check,
        CronTrigger(hour="9-18", minute=0, day_of_week="mon-fri"),
        id="proactive_task_check",
        name="Proactive Task Check",
        replace_existing=True,
    )
    logger.info("Job configurado: Proactive Task Check (cada hora 9-18 L-V)")

    # Alertas de deadline (9 AM y 3 PM)
    scheduler.add_job(
        deadline_alert_check,
        CronTrigger(hour="9,15", minute=0),
        id="deadline_alert",
        name="Deadline Alert Check",
        replace_existing=True,
    )
    logger.info("Job configurado: Deadline Alert Check (9 AM, 3 PM)")

    # Tareas estancadas (5 PM diario)
    scheduler.add_job(
        stale_tasks_check,
        CronTrigger(hour=17, minute=0),
        id="stale_tasks_check",
        name="Stale Tasks Check",
        replace_existing=True,
    )
    logger.info("Job configurado: Stale Tasks Check (5:00 PM)")

    # Seguimiento de completadas (7 PM diario)
    scheduler.add_job(
        task_completion_follow_up,
        CronTrigger(hour=19, minute=0),
        id="task_completion_followup",
        name="Task Completion Follow-up",
        replace_existing=True,
    )
    logger.info("Job configurado: Task Completion Follow-up (7:00 PM)")

    # Recordatorio de bloqueadas (cada 4 horas en horario laboral)
    scheduler.add_job(
        blocked_tasks_reminder,
        CronTrigger(hour="10,14,18", minute=0, day_of_week="mon-fri"),
        id="blocked_tasks_reminder",
        name="Blocked Tasks Reminder",
        replace_existing=True,
    )
    logger.info("Job configurado: Blocked Tasks Reminder (10 AM, 2 PM, 6 PM L-V)")

    # ==================== REMINDER DISPATCHER ====================

    # Despachar recordatorios cada 2 minutos
    scheduler.add_job(
        dispatch_pending_reminders,
        IntervalTrigger(minutes=2),
        id="reminder_dispatcher",
        name="Reminder Dispatcher",
        replace_existing=True,
    )
    logger.info("Job configurado: Reminder Dispatcher (cada 2 min)")

    # Limpieza de recordatorios antiguos (3 AM diario)
    scheduler.add_job(
        cleanup_old_reminders,
        CronTrigger(hour=3, minute=0),
        id="reminder_cleanup",
        name="Reminder Cleanup",
        replace_existing=True,
    )
    logger.info("Job configurado: Reminder Cleanup (3:00 AM)")

    # ==================== PLANNING PROMPTS ====================

    # Prompt de planificación nocturna (9 PM)
    scheduler.add_job(
        send_evening_planning_prompt,
        CronTrigger(hour=21, minute=0),
        id="evening_planning_prompt",
        name="Evening Planning Prompt",
        replace_existing=True,
    )
    logger.info("Job configurado: Evening Planning Prompt (9:00 PM)")

    # Recordatorio del plan matutino (7:30 AM)
    scheduler.add_job(
        send_morning_plan_reminder,
        CronTrigger(hour=7, minute=30),
        id="morning_plan_reminder",
        name="Morning Plan Reminder",
        replace_existing=True,
    )
    logger.info("Job configurado: Morning Plan Reminder (7:30 AM)")

    # ==================== RAG SYNC ====================

    # Sincronización RAG cada 15 minutos
    scheduler.add_job(
        sync_rag_index_job,
        IntervalTrigger(minutes=15),
        id="rag_sync",
        name="RAG Index Sync",
        replace_existing=True,
    )
    logger.info("Job configurado: RAG Index Sync (cada 15 min)")

    # Limpieza de RAG (4 AM diario)
    scheduler.add_job(
        cleanup_stale_rag_entries_job,
        CronTrigger(hour=4, minute=0),
        id="rag_cleanup",
        name="RAG Cleanup",
        replace_existing=True,
    )
    logger.info("Job configurado: RAG Cleanup (4:00 AM)")

    # ==================== INTERACTION FOLLOW-UP ====================

    # Verificar interacciones ignoradas cada 20 minutos (horario laboral)
    scheduler.add_job(
        check_pending_interactions_job,
        CronTrigger(hour="9-18", minute="*/20", day_of_week="mon-fri"),
        id="interaction_follow_up",
        name="Interaction Follow-up",
        replace_existing=True,
    )
    logger.info("Job configurado: Interaction Follow-up (cada 20 min, 9-18 L-V)")

    # Limpieza de interacciones antiguas (5 AM diario)
    scheduler.add_job(
        cleanup_interactions_job,
        CronTrigger(hour=5, minute=0),
        id="interaction_cleanup",
        name="Interaction Cleanup",
        replace_existing=True,
    )
    logger.info("Job configurado: Interaction Cleanup (5:00 AM)")

    # ==================== METRICS & MONITORING ====================

    # Resumen diario de métricas (11:55 PM)
    scheduler.add_job(
        send_daily_metrics_summary,
        CronTrigger(hour=23, minute=55),
        id="daily_metrics_summary",
        name="Daily Metrics Summary",
        replace_existing=True,
    )
    logger.info("Job configurado: Daily Metrics Summary (11:55 PM)")

    # Alertas de rendimiento cada hora
    scheduler.add_job(
        send_performance_alert,
        IntervalTrigger(hours=1),
        id="performance_alert",
        name="Performance Alert Check",
        replace_existing=True,
    )
    logger.info("Job configurado: Performance Alert Check (cada hora)")

    # ==================== JIRA REMINDER ====================

    # Recordatorio de Jira a las 6:30 PM (L-V)
    scheduler.add_job(
        jira_reminder_job,
        CronTrigger(hour=18, minute=30, day_of_week="mon-fri"),
        id="jira_reminder",
        name="Jira Reminder",
        replace_existing=True,
    )
    logger.info("Job configurado: Jira Reminder (6:30 PM L-V)")

    # ==================== SYNC SQLITE <-> NOTION ====================

    # Sincronización completa cada 15 minutos
    scheduler.add_job(
        run_full_sync,
        IntervalTrigger(minutes=15),
        id="full_sync",
        name="Full SQLite-Notion Sync",
        replace_existing=True,
    )
    logger.info("Job configurado: Full Sync (cada 15 min)")

    # Sincronización de tareas cada 5 minutos
    scheduler.add_job(
        sync_tasks_only,
        IntervalTrigger(minutes=5),
        id="tasks_sync",
        name="Tasks Sync (Notion -> SQLite)",
        replace_existing=True,
    )
    logger.info("Job configurado: Tasks Sync (cada 5 min)")

    # Iniciar scheduler si no está corriendo
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler iniciado")

    return scheduler


async def shutdown_scheduler() -> None:
    """Detiene el scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")


def add_one_time_job(
    func,
    run_date: datetime,
    job_id: str,
    **kwargs,
) -> None:
    """Agrega un job de una sola ejecución."""
    scheduler = get_scheduler()
    scheduler.add_job(
        func,
        "date",
        run_date=run_date,
        id=job_id,
        replace_existing=True,
        **kwargs,
    )
    logger.info(f"Job único agregado: {job_id} para {run_date}")


def remove_job(job_id: str) -> bool:
    """Elimina un job por su ID."""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Job eliminado: {job_id}")
        return True
    except Exception as e:
        logger.warning(f"No se pudo eliminar job {job_id}: {e}")
        return False


def get_job_status() -> list[dict]:
    """Obtiene el estado de todos los jobs."""
    scheduler = get_scheduler()
    jobs = []

    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return jobs
