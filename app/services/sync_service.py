"""
Sync Service - Sincronización bidireccional SQLite <-> Notion.

Mantiene los datos consistentes entre la base de datos local y Notion.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_factory
from app.db.models import (
    DailyLog,
    NotionTaskCache,
    ScheduledReminder,
    SyncDirection,
    SyncLog,
    SyncStatus,
    ReminderStatus,
)
from app.services.notion import get_notion_service, NotionDatabase, TaskEstado

logger = logging.getLogger(__name__)


class SyncService:
    """Servicio de sincronización bidireccional."""

    def __init__(self):
        self.notion = get_notion_service()
        self._last_full_sync: datetime | None = None

    @staticmethod
    def _compute_hash(data: dict) -> str:
        """Computa hash SHA256 de datos para detectar cambios."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    async def sync_all(self) -> dict[str, Any]:
        """Ejecuta sincronización completa."""
        logger.info("Iniciando sincronización completa...")
        results = {
            "tasks_synced": 0,
            "reminders_synced": 0,
            "daily_logs_synced": 0,
            "errors": [],
        }

        try:
            # 1. Sincronizar tareas de Notion -> SQLite cache
            tasks_result = await self.sync_tasks_from_notion()
            results["tasks_synced"] = tasks_result.get("synced", 0)

            # 2. Sincronizar recordatorios completados SQLite -> Notion
            reminders_result = await self.sync_reminders_to_notion()
            results["reminders_synced"] = reminders_result.get("synced", 0)

            # 3. Sincronizar daily logs -> Notion (workouts, nutrition)
            logs_result = await self.sync_daily_logs_to_notion()
            results["daily_logs_synced"] = logs_result.get("synced", 0)

            self._last_full_sync = datetime.utcnow()
            logger.info(f"Sincronización completada: {results}")

        except Exception as e:
            logger.error(f"Error en sincronización: {e}")
            results["errors"].append(str(e))

        return results

    async def sync_tasks_from_notion(self) -> dict[str, Any]:
        """Sincroniza tareas de Notion al cache local."""
        result = {"synced": 0, "errors": []}

        try:
            # Obtener tareas de Notion (últimas 100 modificadas)
            notion_tasks = await self.notion.get_all_tasks(limit=100)

            async with async_session_factory() as session:
                for task in notion_tasks:
                    try:
                        await self._upsert_task_cache(session, task)
                        result["synced"] += 1
                    except Exception as e:
                        result["errors"].append(f"Task {task.get('id')}: {e}")

                await session.commit()

        except Exception as e:
            logger.error(f"Error sincronizando tareas: {e}")
            result["errors"].append(str(e))

        return result

    async def _upsert_task_cache(self, session: AsyncSession, task: dict) -> None:
        """Inserta o actualiza tarea en cache local."""
        page_id = task.get("id", "").replace("-", "")
        properties = task.get("properties", {})

        # Extraer datos
        title = ""
        title_prop = properties.get("Tarea", {}).get("title", [])
        if title_prop:
            title = title_prop[0].get("plain_text", "")

        status = properties.get("Estado", {}).get("select", {})
        status_name = status.get("name") if status else None

        priority = properties.get("Prioridad", {}).get("select", {})
        priority_name = priority.get("name") if priority else None

        due_date = None
        fecha_due = properties.get("Fecha Due", {}).get("date")
        if fecha_due and fecha_due.get("start"):
            due_date = fecha_due["start"][:10]

        context = properties.get("Contexto", {}).get("select", {})
        context_name = context.get("name") if context else None

        # Buscar existente
        stmt = select(NotionTaskCache).where(NotionTaskCache.notion_page_id == page_id)
        existing = await session.execute(stmt)
        cached = existing.scalar_one_or_none()

        notion_updated = datetime.fromisoformat(
            task.get("last_edited_time", "").replace("Z", "+00:00")
        ) if task.get("last_edited_time") else None

        if cached:
            # Actualizar
            cached.title = title
            cached.status = status_name
            cached.priority = priority_name
            cached.due_date = due_date
            cached.context = context_name
            cached.notion_updated_at = notion_updated
            cached.cached_at = datetime.utcnow()
            cached.is_stale = False
        else:
            # Insertar
            new_cache = NotionTaskCache(
                notion_page_id=page_id,
                title=title,
                status=status_name,
                priority=priority_name,
                due_date=due_date,
                context=context_name,
                notion_updated_at=notion_updated,
                cached_at=datetime.utcnow(),
            )
            session.add(new_cache)

    async def sync_reminders_to_notion(self) -> dict[str, Any]:
        """Sincroniza recordatorios completados a Notion."""
        result = {"synced": 0, "errors": []}

        try:
            async with async_session_factory() as session:
                # Buscar recordatorios completados que tienen notion_page_id
                stmt = select(ScheduledReminder).where(
                    ScheduledReminder.status == ReminderStatus.COMPLETED,
                    ScheduledReminder.notion_page_id.isnot(None),
                )
                reminders = await session.execute(stmt)

                for reminder in reminders.scalars():
                    try:
                        # Marcar como Done en Notion
                        await self.notion.update_task_status(
                            reminder.notion_page_id,
                            TaskEstado.DONE.value,
                        )

                        # Registrar sync
                        await self._log_sync(
                            session,
                            entity_type="reminder",
                            entity_id=str(reminder.id),
                            notion_page_id=reminder.notion_page_id,
                            direction=SyncDirection.SQLITE_TO_NOTION,
                            status=SyncStatus.SYNCED,
                        )

                        result["synced"] += 1

                    except Exception as e:
                        logger.warning(f"Error sincronizando reminder {reminder.id}: {e}")
                        result["errors"].append(str(e))

                await session.commit()

        except Exception as e:
            logger.error(f"Error en sync_reminders_to_notion: {e}")
            result["errors"].append(str(e))

        return result

    async def sync_daily_logs_to_notion(self) -> dict[str, Any]:
        """Sincroniza daily logs a Notion (workouts y nutrition)."""
        result = {"synced": 0, "errors": []}

        try:
            async with async_session_factory() as session:
                # Obtener logs de hoy y ayer (no sincronizados)
                today = datetime.now().strftime("%Y-%m-%d")
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                stmt = select(DailyLog).where(
                    DailyLog.date.in_([today, yesterday])
                )
                logs = await session.execute(stmt)

                for log in logs.scalars():
                    try:
                        # Sincronizar gym a WORKOUTS
                        if log.gym_completed is not None:
                            await self._sync_workout(log)

                        # Sincronizar nutrición a NUTRITION
                        if log.nutrition_logged:
                            await self._sync_nutrition(log)

                        result["synced"] += 1

                    except Exception as e:
                        logger.warning(f"Error sincronizando log {log.date}: {e}")
                        result["errors"].append(str(e))

                await session.commit()

        except Exception as e:
            logger.error(f"Error en sync_daily_logs: {e}")
            result["errors"].append(str(e))

        return result

    async def _sync_workout(self, log: DailyLog) -> None:
        """Sincroniza workout a Notion."""
        # Buscar si ya existe entrada para esa fecha
        existing = await self.notion.get_workout_by_date(log.date)

        workout_data = {
            "Fecha": log.date,
            "Completado": log.gym_completed,
            "Notas": log.gym_notes or "",
        }

        if existing:
            # Actualizar
            await self.notion.update_workout(existing["id"], workout_data)
        else:
            # Crear nuevo
            await self.notion.create_workout(workout_data)

    async def _sync_nutrition(self, log: DailyLog) -> None:
        """Sincroniza nutrición a Notion."""
        existing = await self.notion.get_nutrition_by_date(log.date)

        nutrition_data = {
            "Fecha": log.date,
            "Total Cal": log.calories_estimate or 0,
        }

        if existing:
            await self.notion.update_nutrition(existing["id"], nutrition_data)
        # Si no existe, no creamos (se crea manualmente en Notion)

    async def _log_sync(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_id: str,
        notion_page_id: str | None,
        direction: SyncDirection,
        status: SyncStatus,
        error_message: str | None = None,
    ) -> None:
        """Registra evento de sincronización."""
        sync_log = SyncLog(
            entity_type=entity_type,
            entity_id=entity_id,
            notion_page_id=notion_page_id,
            sync_direction=direction,
            status=status,
            last_synced_at=datetime.utcnow(),
            error_message=error_message,
        )
        session.add(sync_log)

    async def get_cached_tasks(
        self,
        status: str | None = None,
        context: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Obtiene tareas del cache local (rápido)."""
        async with async_session_factory() as session:
            stmt = select(NotionTaskCache).where(NotionTaskCache.is_stale == False)

            if status:
                stmt = stmt.where(NotionTaskCache.status == status)
            if context:
                stmt = stmt.where(NotionTaskCache.context == context)

            stmt = stmt.limit(limit)
            result = await session.execute(stmt)

            return [
                {
                    "id": t.notion_page_id,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "due_date": t.due_date,
                    "context": t.context,
                }
                for t in result.scalars()
            ]

    async def mark_cache_stale(self) -> None:
        """Marca todo el cache como stale (necesita refresh)."""
        async with async_session_factory() as session:
            stmt = update(NotionTaskCache).values(is_stale=True)
            await session.execute(stmt)
            await session.commit()

    async def get_sync_status(self) -> dict[str, Any]:
        """Obtiene estado actual de sincronización."""
        async with async_session_factory() as session:
            # Contar tareas en cache
            tasks_stmt = select(NotionTaskCache).where(NotionTaskCache.is_stale == False)
            tasks_result = await session.execute(tasks_stmt)
            tasks_count = len(list(tasks_result.scalars()))

            # Último sync log
            sync_stmt = select(SyncLog).order_by(SyncLog.created_at.desc()).limit(1)
            sync_result = await session.execute(sync_stmt)
            last_sync = sync_result.scalar_one_or_none()

            return {
                "cached_tasks": tasks_count,
                "last_full_sync": self._last_full_sync.isoformat() if self._last_full_sync else None,
                "last_sync_event": {
                    "entity": last_sync.entity_type if last_sync else None,
                    "status": last_sync.status.value if last_sync else None,
                    "at": last_sync.created_at.isoformat() if last_sync else None,
                } if last_sync else None,
            }


# Singleton
_sync_service: SyncService | None = None


def get_sync_service() -> SyncService:
    """Obtiene instancia del servicio de sincronización."""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
