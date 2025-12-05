"""Repository para manejo de recordatorios."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReminderPriority, ReminderStatus, ScheduledReminder

logger = logging.getLogger(__name__)


class RemindersRepository:
    """Repository para operaciones CRUD de ScheduledReminder."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, reminder_id: int) -> ScheduledReminder | None:
        """Obtiene un recordatorio por ID."""
        result = await self.session.execute(
            select(ScheduledReminder).where(ScheduledReminder.id == reminder_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        chat_id: str,
        user_id: str,
        title: str,
        scheduled_at: datetime,
        description: str | None = None,
        priority: ReminderPriority = ReminderPriority.NORMAL,
        remind_until: datetime | None = None,
        notion_page_id: str | None = None,
    ) -> ScheduledReminder:
        """Crea un nuevo recordatorio."""
        reminder = ScheduledReminder(
            chat_id=chat_id,
            user_id=user_id,
            title=title,
            description=description,
            scheduled_at=scheduled_at,
            remind_until=remind_until,
            priority=priority,
            notion_page_id=notion_page_id,
        )
        self.session.add(reminder)
        await self.session.flush()
        logger.info(f"Recordatorio creado: {title} para {scheduled_at}")
        return reminder

    async def get_pending(
        self, chat_id: str | None = None, limit: int = 50
    ) -> list[ScheduledReminder]:
        """Obtiene recordatorios pendientes."""
        query = select(ScheduledReminder).where(
            ScheduledReminder.status == ReminderStatus.PENDING
        )

        if chat_id:
            query = query.where(ScheduledReminder.chat_id == chat_id)

        query = query.order_by(ScheduledReminder.scheduled_at.asc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_due_reminders(self, now: datetime | None = None) -> list[ScheduledReminder]:
        """Obtiene recordatorios que deben enviarse ahora."""
        if now is None:
            # Usar hora local (consistente con cómo se crean los recordatorios)
            now = datetime.now()

        result = await self.session.execute(
            select(ScheduledReminder).where(
                and_(
                    ScheduledReminder.status == ReminderStatus.PENDING,
                    ScheduledReminder.scheduled_at <= now,
                    # Excluir los que están en snooze
                    (ScheduledReminder.snooze_until.is_(None))
                    | (ScheduledReminder.snooze_until <= now),
                )
            ).order_by(ScheduledReminder.priority.desc(), ScheduledReminder.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def mark_as_reminded(self, reminder_id: int) -> ScheduledReminder | None:
        """Marca un recordatorio como enviado e incrementa el contador."""
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.last_reminded_at = datetime.now()
            reminder.escalation_count += 1
            await self.session.flush()
            logger.debug(f"Recordatorio {reminder_id} marcado como enviado (count={reminder.escalation_count})")
        return reminder

    async def snooze(
        self, reminder_id: int, minutes: int = 30
    ) -> ScheduledReminder | None:
        """Pospone un recordatorio."""
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.snooze_until = datetime.now() + timedelta(minutes=minutes)
            reminder.status = ReminderStatus.SNOOZED
            await self.session.flush()
            logger.info(f"Recordatorio {reminder_id} pospuesto {minutes} minutos")
        return reminder

    async def acknowledge(self, reminder_id: int) -> ScheduledReminder | None:
        """Marca un recordatorio como reconocido (visto pero no completado)."""
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.status = ReminderStatus.ACKNOWLEDGED
            reminder.updated_at = datetime.now()
            await self.session.flush()
            logger.info(f"Recordatorio {reminder_id} reconocido")
        return reminder

    async def complete(self, reminder_id: int) -> ScheduledReminder | None:
        """Marca un recordatorio como completado."""
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.status = ReminderStatus.COMPLETED
            reminder.updated_at = datetime.now()
            await self.session.flush()
            logger.info(f"Recordatorio {reminder_id} completado")
        return reminder

    async def cancel(self, reminder_id: int) -> ScheduledReminder | None:
        """Cancela un recordatorio."""
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.status = ReminderStatus.CANCELLED
            reminder.updated_at = datetime.now()
            await self.session.flush()
            logger.info(f"Recordatorio {reminder_id} cancelado")
        return reminder

    async def get_by_chat_id(
        self, chat_id: str, include_completed: bool = False
    ) -> list[ScheduledReminder]:
        """Obtiene todos los recordatorios de un chat."""
        query = select(ScheduledReminder).where(ScheduledReminder.chat_id == chat_id)

        if not include_completed:
            query = query.where(
                ScheduledReminder.status.in_([
                    ReminderStatus.PENDING,
                    ReminderStatus.SNOOZED,
                    ReminderStatus.ACKNOWLEDGED,
                ])
            )

        query = query.order_by(ScheduledReminder.scheduled_at.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
