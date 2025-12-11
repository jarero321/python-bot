"""
Scheduler simplificado - Solo triggers.

El scheduler solo dispara triggers, el Brain decide qué hacer.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.config import get_settings
from app.triggers.handlers import (
    trigger_morning_briefing,
    trigger_gym_check,
    trigger_hourly_pulse,
    trigger_evening_reflection,
    trigger_weekly_review,
    trigger_reminder_check,
    trigger_deadline_check,
    trigger_stuck_tasks_check,
    trigger_payday_alert,
    trigger_meal_reminder,
    trigger_proactive_checkin,
    trigger_study_reminder,
)

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
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 120,
            },
        )
    return _scheduler


async def setup_scheduler() -> AsyncIOScheduler:
    """Configura y arranca el scheduler con todos los triggers."""
    scheduler = get_scheduler()

    # ==================== MORNING ====================

    # Morning briefing - 6:30 AM todos los días
    scheduler.add_job(
        trigger_morning_briefing,
        CronTrigger(hour=6, minute=30),
        id="morning_briefing",
        name="Morning Briefing",
        replace_existing=True,
    )
    logger.info("Trigger configurado: morning_briefing (6:30 AM)")

    # ==================== GYM ====================

    # Gym checks - 7:15, 7:30, 7:45 AM lunes a viernes
    for minute, level in [(15, 1), (30, 2), (45, 3)]:
        scheduler.add_job(
            trigger_gym_check,
            CronTrigger(hour=7, minute=minute, day_of_week="mon-fri"),
            id=f"gym_check_{level}",
            name=f"Gym Check (level {level})",
            kwargs={"escalation_level": level},
            replace_existing=True,
        )
    logger.info("Triggers configurados: gym_check (7:15, 7:30, 7:45 L-V)")

    # ==================== HOURLY ====================

    # Hourly pulse - Cada hora de 9 a 18, lunes a viernes
    scheduler.add_job(
        trigger_hourly_pulse,
        CronTrigger(hour="9-18", minute=0, day_of_week="mon-fri"),
        id="hourly_pulse",
        name="Hourly Pulse",
        replace_existing=True,
    )
    logger.info("Trigger configurado: hourly_pulse (9-18 L-V)")

    # ==================== MEAL REMINDERS ====================

    # Desayuno - 8:00 AM todos los días
    scheduler.add_job(
        trigger_meal_reminder,
        CronTrigger(hour=8, minute=0),
        id="meal_breakfast",
        name="Meal Reminder - Breakfast",
        kwargs={"meal_type": "breakfast"},
        replace_existing=True,
    )

    # Almuerzo - 1:30 PM todos los días
    scheduler.add_job(
        trigger_meal_reminder,
        CronTrigger(hour=13, minute=30),
        id="meal_lunch",
        name="Meal Reminder - Lunch",
        kwargs={"meal_type": "lunch"},
        replace_existing=True,
    )

    # Cena - 7:30 PM todos los días
    scheduler.add_job(
        trigger_meal_reminder,
        CronTrigger(hour=19, minute=30),
        id="meal_dinner",
        name="Meal Reminder - Dinner",
        kwargs={"meal_type": "dinner"},
        replace_existing=True,
    )
    logger.info("Triggers configurados: meal_reminders (8AM, 1:30PM, 7:30PM)")

    # ==================== PROACTIVE CHECK-INS ====================

    # Mid-morning check-in - 10:30 AM (L-V)
    scheduler.add_job(
        trigger_proactive_checkin,
        CronTrigger(hour=10, minute=30, day_of_week="mon-fri"),
        id="checkin_morning",
        name="Proactive Check-in Morning",
        kwargs={"period": "morning"},
        replace_existing=True,
    )

    # Afternoon check-in - 3:30 PM (L-V)
    scheduler.add_job(
        trigger_proactive_checkin,
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="checkin_afternoon",
        name="Proactive Check-in Afternoon",
        kwargs={"period": "afternoon"},
        replace_existing=True,
    )
    logger.info("Triggers configurados: proactive_checkin (10:30AM, 3:30PM L-V)")

    # ==================== STUDY ====================

    # Study reminder - 5:30 PM todos los días
    scheduler.add_job(
        trigger_study_reminder,
        CronTrigger(hour=17, minute=30),
        id="study_reminder",
        name="Study Reminder",
        replace_existing=True,
    )
    logger.info("Trigger configurado: study_reminder (5:30 PM)")

    # ==================== EVENING ====================

    # Evening reflection - 9 PM todos los días
    scheduler.add_job(
        trigger_evening_reflection,
        CronTrigger(hour=21, minute=0),
        id="evening_reflection",
        name="Evening Reflection",
        replace_existing=True,
    )
    logger.info("Trigger configurado: evening_reflection (9 PM)")

    # ==================== WEEKLY ====================

    # Weekly review - Domingo 10 AM
    scheduler.add_job(
        trigger_weekly_review,
        CronTrigger(hour=10, minute=0, day_of_week="sun"),
        id="weekly_review",
        name="Weekly Review",
        replace_existing=True,
    )
    logger.info("Trigger configurado: weekly_review (Domingo 10 AM)")

    # ==================== REMINDERS ====================

    # Check reminders - Cada 2 minutos
    scheduler.add_job(
        trigger_reminder_check,
        IntervalTrigger(minutes=2),
        id="reminder_check",
        name="Reminder Check",
        replace_existing=True,
    )
    logger.info("Trigger configurado: reminder_check (cada 2 min)")

    # ==================== DEADLINES & STUCK ====================

    # Deadline check - 9 AM y 3 PM
    scheduler.add_job(
        trigger_deadline_check,
        CronTrigger(hour="9,15", minute=0),
        id="deadline_check",
        name="Deadline Check",
        replace_existing=True,
    )
    logger.info("Trigger configurado: deadline_check (9 AM, 3 PM)")

    # Stuck tasks check - 5 PM diario
    scheduler.add_job(
        trigger_stuck_tasks_check,
        CronTrigger(hour=17, minute=0),
        id="stuck_tasks_check",
        name="Stuck Tasks Check",
        replace_existing=True,
    )
    logger.info("Trigger configurado: stuck_tasks_check (5 PM)")

    # ==================== FINANCE ====================

    # Payday alerts - Días 13, 14, 15, 28, 29, 30
    scheduler.add_job(
        trigger_payday_alert,
        CronTrigger(hour=9, minute=0, day="13,14,28,29"),
        id="payday_pre",
        name="Payday Pre-Alert",
        kwargs={"is_pre": True},
        replace_existing=True,
    )
    scheduler.add_job(
        trigger_payday_alert,
        CronTrigger(hour=18, minute=0, day="15,30"),
        id="payday_post",
        name="Payday Post-Alert",
        kwargs={"is_pre": False},
        replace_existing=True,
    )
    logger.info("Triggers configurados: payday_alert (pre y post)")

    # ==================== START ====================

    if not scheduler.running:
        scheduler.start()
        logger.info(f"Scheduler iniciado con {len(scheduler.get_jobs())} jobs")

    return scheduler


async def shutdown_scheduler() -> None:
    """Detiene el scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")


def schedule_one_time_trigger(
    trigger_func,
    run_at: datetime,
    trigger_id: str,
    **kwargs
) -> None:
    """
    Programa un trigger de una sola ejecución.

    Útil para reminders dinámicos.
    """
    scheduler = get_scheduler()
    scheduler.add_job(
        trigger_func,
        DateTrigger(run_date=run_at),
        id=trigger_id,
        kwargs=kwargs,
        replace_existing=True,
    )
    logger.info(f"Trigger único programado: {trigger_id} para {run_at}")


def remove_trigger(trigger_id: str) -> bool:
    """Elimina un trigger programado."""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(trigger_id)
        logger.info(f"Trigger eliminado: {trigger_id}")
        return True
    except Exception as e:
        logger.warning(f"No se pudo eliminar trigger {trigger_id}: {e}")
        return False


def get_scheduled_triggers() -> list[dict]:
    """Obtiene lista de triggers programados."""
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]
