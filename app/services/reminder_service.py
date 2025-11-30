"""Servicio para gestión de recordatorios persistentes."""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import ScheduledReminder, ReminderStatus, ReminderPriority

logger = logging.getLogger(__name__)


class ReminderService:
    """
    Servicio para gestionar recordatorios persistentes.

    Funcionalidades:
    - Crear recordatorios con diferentes prioridades
    - Programar recordatorios para tareas de Notion
    - Gestionar snooze y escalación
    - Obtener recordatorios pendientes
    """

    async def create_reminder(
        self,
        chat_id: str,
        user_id: str,
        title: str,
        scheduled_at: datetime,
        description: str | None = None,
        priority: ReminderPriority = ReminderPriority.NORMAL,
        notion_page_id: str | None = None,
        remind_until: datetime | None = None,
    ) -> ScheduledReminder:
        """
        Crea un nuevo recordatorio.

        Args:
            chat_id: ID del chat de Telegram
            user_id: ID del usuario
            title: Título del recordatorio
            scheduled_at: Cuándo enviar el recordatorio
            description: Descripción opcional
            priority: Prioridad del recordatorio
            notion_page_id: ID de página de Notion relacionada
            remind_until: Hasta cuándo seguir recordando

        Returns:
            ScheduledReminder creado
        """
        async with get_session() as session:
            reminder = ScheduledReminder(
                chat_id=chat_id,
                user_id=user_id,
                title=title,
                description=description,
                scheduled_at=scheduled_at,
                remind_until=remind_until or (scheduled_at + timedelta(hours=24)),
                priority=priority,
                notion_page_id=notion_page_id,
                status=ReminderStatus.PENDING,
            )
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)

            logger.info(f"Recordatorio creado: {title} para {scheduled_at}")
            return reminder

    async def create_task_reminders(
        self,
        chat_id: str,
        user_id: str,
        task_title: str,
        notion_page_id: str,
        fecha_due: str | None,
        priority: str = "normal",
    ) -> list[ScheduledReminder]:
        """
        Crea recordatorios automáticos para una tarea.

        Args:
            chat_id: ID del chat
            user_id: ID del usuario
            task_title: Título de la tarea
            notion_page_id: ID de la tarea en Notion
            fecha_due: Fecha límite (YYYY-MM-DD)
            priority: Prioridad de la tarea

        Returns:
            Lista de recordatorios creados
        """
        if not fecha_due:
            return []

        reminders = []
        due_date = datetime.strptime(fecha_due, "%Y-%m-%d")

        # Mapear prioridad
        priority_map = {
            "urgente": ReminderPriority.URGENT,
            "alta": ReminderPriority.HIGH,
            "normal": ReminderPriority.NORMAL,
            "baja": ReminderPriority.LOW,
        }
        reminder_priority = priority_map.get(priority.lower(), ReminderPriority.NORMAL)

        # Recordatorio un día antes (9 AM)
        day_before = due_date - timedelta(days=1)
        day_before = day_before.replace(hour=9, minute=0, second=0)

        if day_before > datetime.now():
            reminder = await self.create_reminder(
                chat_id=chat_id,
                user_id=user_id,
                title=f"📅 Mañana vence: {task_title}",
                description=f"La tarea '{task_title}' vence mañana ({fecha_due})",
                scheduled_at=day_before,
                priority=reminder_priority,
                notion_page_id=notion_page_id,
            )
            reminders.append(reminder)

        # Para tareas urgentes/altas, recordatorio el mismo día
        if priority.lower() in ["urgente", "alta"]:
            same_day = due_date.replace(hour=7, minute=0, second=0)

            if same_day > datetime.now():
                reminder = await self.create_reminder(
                    chat_id=chat_id,
                    user_id=user_id,
                    title=f"🔥 HOY vence: {task_title}",
                    description=f"La tarea '{task_title}' vence HOY",
                    scheduled_at=same_day,
                    priority=ReminderPriority.URGENT,
                    notion_page_id=notion_page_id,
                )
                reminders.append(reminder)

        return reminders

    async def get_pending_reminders(
        self,
        chat_id: str | None = None,
        before: datetime | None = None,
    ) -> list[ScheduledReminder]:
        """
        Obtiene recordatorios pendientes.

        Args:
            chat_id: Filtrar por chat (opcional)
            before: Recordatorios programados antes de esta fecha

        Returns:
            Lista de recordatorios pendientes
        """
        async with get_session() as session:
            query = select(ScheduledReminder).where(
                ScheduledReminder.status == ReminderStatus.PENDING
            )

            if chat_id:
                query = query.where(ScheduledReminder.chat_id == chat_id)

            if before:
                query = query.where(ScheduledReminder.scheduled_at <= before)

            # Excluir los que están en snooze
            query = query.where(
                or_(
                    ScheduledReminder.snooze_until.is_(None),
                    ScheduledReminder.snooze_until <= datetime.now()
                )
            )

            query = query.order_by(ScheduledReminder.scheduled_at)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_due_reminders(self) -> list[ScheduledReminder]:
        """
        Obtiene recordatorios que deben enviarse ahora.

        Returns:
            Lista de recordatorios que deben enviarse
        """
        now = datetime.now()

        async with get_session() as session:
            query = select(ScheduledReminder).where(
                and_(
                    ScheduledReminder.status == ReminderStatus.PENDING,
                    ScheduledReminder.scheduled_at <= now,
                    or_(
                        ScheduledReminder.snooze_until.is_(None),
                        ScheduledReminder.snooze_until <= now
                    ),
                    or_(
                        ScheduledReminder.remind_until.is_(None),
                        ScheduledReminder.remind_until >= now
                    )
                )
            ).order_by(ScheduledReminder.priority.desc(), ScheduledReminder.scheduled_at)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def mark_acknowledged(self, reminder_id: int) -> bool:
        """Marca un recordatorio como reconocido."""
        async with get_session() as session:
            result = await session.execute(
                update(ScheduledReminder)
                .where(ScheduledReminder.id == reminder_id)
                .values(
                    status=ReminderStatus.ACKNOWLEDGED,
                    updated_at=datetime.now()
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def mark_completed(self, reminder_id: int) -> bool:
        """Marca un recordatorio como completado."""
        async with get_session() as session:
            result = await session.execute(
                update(ScheduledReminder)
                .where(ScheduledReminder.id == reminder_id)
                .values(
                    status=ReminderStatus.COMPLETED,
                    updated_at=datetime.now()
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def snooze_reminder(
        self,
        reminder_id: int,
        snooze_minutes: int = 30,
    ) -> bool:
        """
        Pospone un recordatorio.

        Args:
            reminder_id: ID del recordatorio
            snooze_minutes: Minutos a posponer

        Returns:
            True si se actualizó correctamente
        """
        snooze_until = datetime.now() + timedelta(minutes=snooze_minutes)

        async with get_session() as session:
            result = await session.execute(
                update(ScheduledReminder)
                .where(ScheduledReminder.id == reminder_id)
                .values(
                    snooze_until=snooze_until,
                    status=ReminderStatus.SNOOZED,
                    escalation_count=ScheduledReminder.escalation_count + 1,
                    last_reminded_at=datetime.now(),
                    updated_at=datetime.now()
                )
            )
            await session.commit()

            logger.info(f"Recordatorio {reminder_id} pospuesto hasta {snooze_until}")
            return result.rowcount > 0

    async def cancel_reminder(self, reminder_id: int) -> bool:
        """Cancela un recordatorio."""
        async with get_session() as session:
            result = await session.execute(
                update(ScheduledReminder)
                .where(ScheduledReminder.id == reminder_id)
                .values(
                    status=ReminderStatus.CANCELLED,
                    updated_at=datetime.now()
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def cancel_task_reminders(self, notion_page_id: str) -> int:
        """
        Cancela todos los recordatorios de una tarea.

        Args:
            notion_page_id: ID de la página de Notion

        Returns:
            Número de recordatorios cancelados
        """
        async with get_session() as session:
            result = await session.execute(
                update(ScheduledReminder)
                .where(
                    and_(
                        ScheduledReminder.notion_page_id == notion_page_id,
                        ScheduledReminder.status == ReminderStatus.PENDING
                    )
                )
                .values(
                    status=ReminderStatus.CANCELLED,
                    updated_at=datetime.now()
                )
            )
            await session.commit()

            logger.info(f"Cancelados {result.rowcount} recordatorios para tarea {notion_page_id}")
            return result.rowcount

    async def update_reminder_time(
        self,
        reminder_id: int,
        new_time: datetime,
    ) -> bool:
        """Actualiza la hora de un recordatorio."""
        async with get_session() as session:
            result = await session.execute(
                update(ScheduledReminder)
                .where(ScheduledReminder.id == reminder_id)
                .values(
                    scheduled_at=new_time,
                    status=ReminderStatus.PENDING,
                    snooze_until=None,
                    updated_at=datetime.now()
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def get_upcoming_reminders(
        self,
        chat_id: str,
        hours: int = 24,
    ) -> list[ScheduledReminder]:
        """
        Obtiene recordatorios próximos.

        Args:
            chat_id: ID del chat
            hours: Próximas N horas

        Returns:
            Lista de recordatorios próximos
        """
        now = datetime.now()
        until = now + timedelta(hours=hours)

        async with get_session() as session:
            query = select(ScheduledReminder).where(
                and_(
                    ScheduledReminder.chat_id == chat_id,
                    ScheduledReminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SNOOZED]),
                    ScheduledReminder.scheduled_at <= until
                )
            ).order_by(ScheduledReminder.scheduled_at)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def cleanup_old_reminders(self, days: int = 30) -> int:
        """
        Limpia recordatorios antiguos completados/cancelados.

        Args:
            days: Recordatorios más antiguos que N días

        Returns:
            Número de recordatorios eliminados
        """
        from sqlalchemy import delete

        cutoff = datetime.now() - timedelta(days=days)

        async with get_session() as session:
            result = await session.execute(
                delete(ScheduledReminder).where(
                    and_(
                        ScheduledReminder.status.in_([
                            ReminderStatus.COMPLETED,
                            ReminderStatus.CANCELLED,
                            ReminderStatus.ACKNOWLEDGED
                        ]),
                        ScheduledReminder.updated_at < cutoff
                    )
                )
            )
            await session.commit()

            logger.info(f"Limpiados {result.rowcount} recordatorios antiguos")
            return result.rowcount


# Singleton
_reminder_service: ReminderService | None = None


def get_reminder_service() -> ReminderService:
    """Obtiene la instancia del servicio de recordatorios."""
    global _reminder_service
    if _reminder_service is None:
        _reminder_service = ReminderService()
    return _reminder_service
