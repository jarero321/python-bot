"""Jobs del scheduler."""

from app.scheduler.jobs.morning_briefing import morning_briefing_job
from app.scheduler.jobs.hourly_checkin import hourly_checkin_job
from app.scheduler.jobs.gym_reminder import (
    gym_reminder_job,
    confirm_gym,
    reset_gym_confirmation,
)
from app.scheduler.jobs.nutrition_reminder import nutrition_reminder_job
from app.scheduler.jobs.persistent_reminders import check_persistent_reminders_job
from app.scheduler.jobs.weekly_review import weekly_review_job
from app.scheduler.jobs.payday_alert import pre_payday_job, post_payday_job
from app.scheduler.jobs.study_reminder import study_reminder_job

__all__ = [
    # Core jobs
    "morning_briefing_job",
    "hourly_checkin_job",
    "nutrition_reminder_job",
    "check_persistent_reminders_job",
    # Gym
    "gym_reminder_job",
    "confirm_gym",
    "reset_gym_confirmation",
    # Weekly
    "weekly_review_job",
    # Finance
    "pre_payday_job",
    "post_payday_job",
    # Study
    "study_reminder_job",
]
