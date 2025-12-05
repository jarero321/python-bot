"""
Schedule Helpers - Utilidades para manejo de horarios y días.

Centraliza la lógica de:
- Detección de fin de semana
- Modo silencioso
- Horarios laborales
"""

from datetime import datetime
from enum import Enum


class DayMode(str, Enum):
    """Modo del día para notificaciones."""

    WORKDAY = "workday"       # Lunes a Viernes - todas las notificaciones
    WEEKEND_LIGHT = "weekend_light"  # Sábado/Domingo - solo briefing ligero
    SILENT = "silent"         # Modo silencioso total


def get_day_mode(dt: datetime | None = None) -> DayMode:
    """
    Determina el modo del día actual.

    Returns:
        DayMode: WORKDAY (L-V), WEEKEND_LIGHT (S-D)
    """
    if dt is None:
        dt = datetime.now()

    # 0=Lunes, 5=Sábado, 6=Domingo
    if dt.weekday() >= 5:
        return DayMode.WEEKEND_LIGHT

    return DayMode.WORKDAY


def is_weekend(dt: datetime | None = None) -> bool:
    """Retorna True si es sábado o domingo."""
    if dt is None:
        dt = datetime.now()
    return dt.weekday() >= 5


def is_workday(dt: datetime | None = None) -> bool:
    """Retorna True si es día laboral (L-V)."""
    return not is_weekend(dt)


def is_work_hours(dt: datetime | None = None) -> bool:
    """
    Retorna True si está en horario laboral (9-18).
    """
    if dt is None:
        dt = datetime.now()
    return 9 <= dt.hour < 18


def should_send_notification(
    notification_type: str,
    dt: datetime | None = None,
) -> bool:
    """
    Determina si se debe enviar una notificación según el tipo y día.

    Args:
        notification_type: Tipo de notificación
            - "morning_briefing": Siempre (ligero en weekend)
            - "checkin": Solo días laborales
            - "gym": Solo días laborales
            - "reminder": Siempre
            - "deadline": Siempre (urgentes)
            - "jira_reminder": Solo días laborales
        dt: Fecha/hora a evaluar

    Returns:
        True si se debe enviar
    """
    mode = get_day_mode(dt)

    # Notificaciones que siempre van
    always_send = ["morning_briefing", "reminder", "deadline", "critical"]
    if notification_type in always_send:
        return True

    # Notificaciones solo para días laborales
    workday_only = ["checkin", "gym", "nutrition", "hourly", "jira_reminder", "proactive"]
    if notification_type in workday_only:
        return mode == DayMode.WORKDAY

    # Por defecto, enviar
    return True


def get_weekend_briefing_message() -> str:
    """
    Genera mensaje de briefing ligero para fin de semana.
    """
    now = datetime.now()
    day_name = "Sábado" if now.weekday() == 5 else "Domingo"

    return (
        f"<b>Buenos días, {day_name}</b>\n\n"
        "Es fin de semana. Hoy toca descanso.\n\n"
        "Si tienes algo pendiente urgente, dímelo.\n"
        "De lo contrario, disfruta tu día."
    )
