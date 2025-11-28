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
    from app.scheduler.jobs.morning_briefing import morning_briefing_job
    from app.scheduler.jobs.hourly_checkin import hourly_checkin_job
    from app.scheduler.jobs.gym_reminder import gym_reminder_job
    from app.scheduler.jobs.nutrition_reminder import nutrition_reminder_job
    from app.scheduler.jobs.persistent_reminders import check_persistent_reminders_job
    from app.scheduler.jobs.weekly_review import weekly_review_job
    from app.scheduler.jobs.payday_alert import pre_payday_job, post_payday_job
    from app.scheduler.jobs.study_reminder import study_reminder_job

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
