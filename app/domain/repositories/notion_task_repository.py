"""
NotionTaskRepository - Implementación del repositorio de tareas usando Notion.

Este repositorio traduce entre las entidades del dominio y la estructura
de datos de Notion, manteniendo la lógica de negocio desacoplada.
"""

import logging
from datetime import date, datetime
from typing import Any

from app.domain.entities.task import (
    Task,
    TaskFilter,
    TaskStatus,
    TaskPriority,
    TaskComplexity,
    TaskEnergy,
    TaskTimeBlock,
)
from app.domain.repositories.base import ITaskRepository
from app.services.notion import (
    get_notion_service,
    NotionService,
    TaskEstado,
    TaskPrioridad,
    TaskComplejidad,
    TaskEnergia,
    TaskBloque,
    TaskContexto,
)

logger = logging.getLogger(__name__)


class NotionTaskRepository(ITaskRepository):
    """
    Repositorio de tareas usando Notion como backend.

    Responsabilidades:
    - Traducir entre Task (dominio) y estructura Notion
    - Ejecutar queries contra Notion API
    - Cachear resultados cuando apropiado
    """

    def __init__(self, notion_service: NotionService | None = None):
        self._notion = notion_service or get_notion_service()

    # ==================== Mappers ====================

    def _map_status_to_notion(self, status: TaskStatus) -> TaskEstado:
        """Mapea estado del dominio a Notion."""
        mapping = {
            TaskStatus.BACKLOG: TaskEstado.BACKLOG,
            TaskStatus.PLANNED: TaskEstado.PLANNED,
            TaskStatus.TODAY: TaskEstado.TODAY,
            TaskStatus.DOING: TaskEstado.DOING,
            TaskStatus.PAUSED: TaskEstado.PAUSED,
            TaskStatus.DONE: TaskEstado.DONE,
            TaskStatus.CANCELLED: TaskEstado.CANCELLED,
        }
        return mapping.get(status, TaskEstado.BACKLOG)

    def _map_status_from_notion(self, notion_status: str) -> TaskStatus:
        """Mapea estado de Notion a dominio."""
        mapping = {
            "📥 Backlog": TaskStatus.BACKLOG,
            "📋 Planned": TaskStatus.PLANNED,
            "🎯 Today": TaskStatus.TODAY,
            "⚡ Doing": TaskStatus.DOING,
            "⏸️ Paused": TaskStatus.PAUSED,
            "✅ Done": TaskStatus.DONE,
            "❌ Cancelled": TaskStatus.CANCELLED,
        }
        return mapping.get(notion_status, TaskStatus.BACKLOG)

    def _map_priority_to_notion(self, priority: TaskPriority) -> TaskPrioridad:
        """Mapea prioridad del dominio a Notion."""
        mapping = {
            TaskPriority.URGENT: TaskPrioridad.URGENTE,
            TaskPriority.HIGH: TaskPrioridad.ALTA,
            TaskPriority.NORMAL: TaskPrioridad.NORMAL,
            TaskPriority.LOW: TaskPrioridad.BAJA,
        }
        return mapping.get(priority, TaskPrioridad.NORMAL)

    def _map_priority_from_notion(self, notion_priority: str) -> TaskPriority:
        """Mapea prioridad de Notion a dominio."""
        mapping = {
            "🔥 Urgente": TaskPriority.URGENT,
            "⚡ Alta": TaskPriority.HIGH,
            "🔄 Normal": TaskPriority.NORMAL,
            "🧊 Baja": TaskPriority.LOW,
        }
        return mapping.get(notion_priority, TaskPriority.NORMAL)

    def _map_complexity_from_notion(self, notion_complexity: str) -> TaskComplexity | None:
        """Mapea complejidad de Notion a dominio."""
        mapping = {
            "🟢 Quick (<30m)": TaskComplexity.QUICK,
            "🟡 Standard (30m-2h)": TaskComplexity.STANDARD,
            "🔴 Heavy (2-4h)": TaskComplexity.HEAVY,
            "⚫ Epic (4h+)": TaskComplexity.EPIC,
        }
        return mapping.get(notion_complexity)

    def _map_energy_from_notion(self, notion_energy: str) -> TaskEnergy | None:
        """Mapea energía de Notion a dominio."""
        mapping = {
            "🧠 Deep Work": TaskEnergy.DEEP_WORK,
            "💪 Medium": TaskEnergy.MEDIUM,
            "😴 Low": TaskEnergy.LOW,
        }
        return mapping.get(notion_energy)

    def _map_timeblock_from_notion(self, notion_block: str) -> TaskTimeBlock | None:
        """Mapea bloque de tiempo de Notion a dominio."""
        mapping = {
            "🌅 Morning": TaskTimeBlock.MORNING,
            "☀️ Afternoon": TaskTimeBlock.AFTERNOON,
            "🌆 Evening": TaskTimeBlock.EVENING,
        }
        return mapping.get(notion_block)

    def _map_complexity_to_notion(self, complexity: TaskComplexity) -> TaskComplejidad:
        """Mapea complejidad del dominio a Notion."""
        mapping = {
            TaskComplexity.QUICK: TaskComplejidad.QUICK,
            TaskComplexity.STANDARD: TaskComplejidad.STANDARD,
            TaskComplexity.HEAVY: TaskComplejidad.HEAVY,
            TaskComplexity.EPIC: TaskComplejidad.EPIC,
        }
        return mapping.get(complexity, TaskComplejidad.STANDARD)

    def _map_energy_to_notion(self, energy: TaskEnergy) -> TaskEnergia:
        """Mapea energía del dominio a Notion."""
        mapping = {
            TaskEnergy.DEEP_WORK: TaskEnergia.DEEP_WORK,
            TaskEnergy.MEDIUM: TaskEnergia.MEDIUM,
            TaskEnergy.LOW: TaskEnergia.LOW,
        }
        return mapping.get(energy, TaskEnergia.MEDIUM)

    def _map_timeblock_to_notion(self, time_block: TaskTimeBlock) -> TaskBloque:
        """Mapea bloque de tiempo del dominio a Notion."""
        mapping = {
            TaskTimeBlock.MORNING: TaskBloque.MORNING,
            TaskTimeBlock.AFTERNOON: TaskBloque.AFTERNOON,
            TaskTimeBlock.EVENING: TaskBloque.EVENING,
        }
        return mapping.get(time_block, TaskBloque.MORNING)

    def _notion_to_task(self, notion_data: dict[str, Any]) -> Task:
        """Convierte datos de Notion a entidad Task."""
        props = notion_data.get("properties", {})

        # Extraer título
        title_prop = props.get("Tarea", {}).get("title", [])
        title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

        # Extraer estado
        estado_prop = props.get("Estado", {}).get("select", {})
        estado = estado_prop.get("name", "") if estado_prop else ""

        # Extraer prioridad
        prioridad_prop = props.get("Prioridad", {}).get("select", {})
        prioridad = prioridad_prop.get("name", "") if prioridad_prop else ""

        # Extraer complejidad
        complejidad_prop = props.get("Complejidad", {}).get("select", {})
        complejidad = complejidad_prop.get("name", "") if complejidad_prop else None

        # Extraer energía
        energia_prop = props.get("Energia", {}).get("select", {})
        energia = energia_prop.get("name", "") if energia_prop else None

        # Extraer bloque
        bloque_prop = props.get("Bloque", {}).get("select", {})
        bloque = bloque_prop.get("name", "") if bloque_prop else None

        # Extraer fechas
        fecha_due_prop = props.get("Fecha Due", {}).get("date", {})
        fecha_due = None
        if fecha_due_prop and fecha_due_prop.get("start"):
            try:
                fecha_due = date.fromisoformat(fecha_due_prop["start"])
            except ValueError:
                pass

        fecha_do_prop = props.get("Fecha Do", {}).get("date", {})
        fecha_do = None
        if fecha_do_prop and fecha_do_prop.get("start"):
            try:
                fecha_do = date.fromisoformat(fecha_do_prop["start"])
            except ValueError:
                pass

        # Extraer proyecto
        proyecto_prop = props.get("Proyecto", {}).get("relation", [])
        proyecto_id = proyecto_prop[0].get("id") if proyecto_prop else None

        # Extraer contexto
        contexto_prop = props.get("Contexto", {}).get("select", {})
        contexto = contexto_prop.get("name", "") if contexto_prop else None

        # Extraer notas
        notas_prop = props.get("Notas", {}).get("rich_text", [])
        notas = notas_prop[0].get("text", {}).get("content", "") if notas_prop else None

        # Extraer subtareas
        subtareas_prop = props.get("Subtareas", {}).get("relation", [])
        subtask_ids = [st.get("id") for st in subtareas_prop] if subtareas_prop else []

        return Task(
            id=notion_data.get("id", ""),
            title=title,
            status=self._map_status_from_notion(estado),
            priority=self._map_priority_from_notion(prioridad),
            complexity=self._map_complexity_from_notion(complejidad) if complejidad else None,
            energy=self._map_energy_from_notion(energia) if energia else None,
            time_block=self._map_timeblock_from_notion(bloque) if bloque else None,
            due_date=fecha_due,
            scheduled_date=fecha_do,
            project_id=proyecto_id,
            context=contexto,
            notes=notas,
            subtask_ids=subtask_ids,
            created_at=datetime.fromisoformat(
                notion_data.get("created_time", "").replace("Z", "+00:00")
            ) if notion_data.get("created_time") else None,
            _raw=notion_data,
        )

    def _task_to_notion_properties(self, task: Task) -> dict[str, Any]:
        """Convierte Task a properties de Notion."""
        properties: dict[str, Any] = {
            "Tarea": {"title": [{"text": {"content": task.title}}]},
            "Estado": {"select": {"name": self._map_status_to_notion(task.status).value}},
        }

        if task.priority:
            properties["Prioridad"] = {
                "select": {"name": self._map_priority_to_notion(task.priority).value}
            }

        if task.complexity:
            properties["Complejidad"] = {
                "select": {"name": self._map_complexity_to_notion(task.complexity).value}
            }

        if task.energy:
            properties["Energia"] = {
                "select": {"name": self._map_energy_to_notion(task.energy).value}
            }

        if task.time_block:
            properties["Bloque"] = {
                "select": {"name": self._map_timeblock_to_notion(task.time_block).value}
            }

        if task.estimated_minutes:
            if task.estimated_minutes >= 60:
                hours = task.estimated_minutes // 60
                mins = task.estimated_minutes % 60
                tiempo_est = f"{hours}h{mins}m" if mins else f"{hours}h"
            else:
                tiempo_est = f"{task.estimated_minutes}m"
            properties["Tiempo Est"] = {"rich_text": [{"text": {"content": tiempo_est}}]}

        if task.due_date:
            properties["Fecha Due"] = {"date": {"start": task.due_date.isoformat()}}

        if task.scheduled_date:
            properties["Fecha Do"] = {"date": {"start": task.scheduled_date.isoformat()}}

        if task.project_id:
            properties["Proyecto"] = {"relation": [{"id": task.project_id}]}

        if task.notes:
            properties["Notas"] = {"rich_text": [{"text": {"content": task.notes}}]}

        return properties

    # ==================== CRUD ====================

    async def get_by_id(self, id: str) -> Task | None:
        """Obtiene una tarea por su ID."""
        try:
            page = await self._notion.get_page(id)
            if page:
                return self._notion_to_task(page)
            return None
        except Exception as e:
            logger.error(f"Error obteniendo tarea {id}: {e}")
            return None

    async def create(self, task: Task) -> Task:
        """Crea una nueva tarea con todos los datos enriquecidos."""
        # Mapear campos opcionales
        complejidad = None
        if task.complexity:
            complejidad = self._map_complexity_to_notion(task.complexity)

        energia = None
        if task.energy:
            energia = self._map_energy_to_notion(task.energy)

        bloque = None
        if task.time_block:
            bloque = self._map_timeblock_to_notion(task.time_block)

        # Formatear tiempo estimado
        tiempo_est = None
        if task.estimated_minutes:
            if task.estimated_minutes >= 60:
                hours = task.estimated_minutes // 60
                mins = task.estimated_minutes % 60
                tiempo_est = f"{hours}h{mins}m" if mins else f"{hours}h"
            else:
                tiempo_est = f"{task.estimated_minutes}m"

        result = await self._notion.create_task(
            tarea=task.title,
            estado=self._map_status_to_notion(task.status),
            prioridad=self._map_priority_to_notion(task.priority) if task.priority else None,
            fecha_due=task.due_date.isoformat() if task.due_date else None,
            fecha_do=task.scheduled_date.isoformat() if task.scheduled_date else None,
            proyecto_id=task.project_id,
            notas=task.notes,
            complejidad=complejidad,
            energia=energia,
            bloque=bloque,
            tiempo_est=tiempo_est,
            parent_task_id=task.parent_task_id,
        )

        if result:
            return self._notion_to_task(result)
        raise Exception("Error creando tarea en Notion")

    async def update(self, task: Task) -> Task:
        """Actualiza una tarea existente."""
        properties = self._task_to_notion_properties(task)

        try:
            result = await self._notion.client.pages.update(
                page_id=task.id,
                properties=properties,
            )
            return self._notion_to_task(result)
        except Exception as e:
            logger.error(f"Error actualizando tarea {task.id}: {e}")
            raise

    async def delete(self, id: str) -> bool:
        """Archiva una tarea (Notion no permite eliminar)."""
        try:
            await self._notion.client.pages.update(
                page_id=id,
                archived=True,
            )
            return True
        except Exception as e:
            logger.error(f"Error eliminando tarea {id}: {e}")
            return False

    # ==================== Queries ====================

    async def find(self, filter: TaskFilter) -> list[Task]:
        """Busca tareas según filtros."""
        # Por ahora, usar get_pending_tasks y filtrar
        # En el futuro, construir query de Notion dinámicamente
        tasks = await self._notion.get_pending_tasks(limit=filter.limit)
        result = [self._notion_to_task(t) for t in tasks]

        # Aplicar filtros adicionales en memoria
        if filter.status:
            statuses = [filter.status] if isinstance(filter.status, TaskStatus) else filter.status
            result = [t for t in result if t.status in statuses]

        if filter.priority:
            priorities = [filter.priority] if isinstance(filter.priority, TaskPriority) else filter.priority
            result = [t for t in result if t.priority in priorities]

        if filter.project_id:
            result = [t for t in result if t.project_id == filter.project_id]

        if filter.is_overdue:
            result = [t for t in result if t.is_overdue]

        return result[:filter.limit]

    async def get_for_today(self) -> list[Task]:
        """Obtiene tareas programadas para hoy."""
        tasks = await self._notion.get_tasks_for_today()
        return [self._notion_to_task(t) for t in tasks]

    async def get_pending(self, limit: int = 50) -> list[Task]:
        """Obtiene tareas pendientes."""
        tasks = await self._notion.get_pending_tasks(limit=limit)
        return [self._notion_to_task(t) for t in tasks]

    async def get_overdue(self) -> list[Task]:
        """Obtiene tareas vencidas."""
        pending = await self.get_pending(limit=100)
        return [t for t in pending if t.is_overdue]

    async def get_by_project(self, project_id: str) -> list[Task]:
        """Obtiene tareas de un proyecto."""
        pending = await self.get_pending(limit=100)
        return [t for t in pending if t.project_id == project_id]

    async def get_by_status(self, status: TaskStatus) -> list[Task]:
        """Obtiene tareas por estado."""
        notion_status = self._map_status_to_notion(status)
        tasks = await self._notion.get_tasks_by_estado(notion_status)
        return [self._notion_to_task(t) for t in tasks]

    async def get_by_priority(self, priority: TaskPriority) -> list[Task]:
        """Obtiene tareas por prioridad."""
        pending = await self.get_pending(limit=100)
        return [t for t in pending if t.priority == priority]

    async def get_scheduled_for(self, target_date: date) -> list[Task]:
        """Obtiene tareas programadas para una fecha."""
        pending = await self.get_pending(limit=100)
        return [t for t in pending if t.scheduled_date == target_date]

    async def get_subtasks(self, parent_id: str) -> list[Task]:
        """Obtiene subtareas de una tarea."""
        subtasks = await self._notion.get_subtasks(parent_id)
        return [self._notion_to_task(t) for t in subtasks]

    # ==================== Updates Específicos ====================

    async def update_status(self, id: str, status: TaskStatus) -> Task | None:
        """Actualiza el estado de una tarea."""
        notion_status = self._map_status_to_notion(status)
        result = await self._notion.update_task_estado(id, notion_status)
        if result:
            return self._notion_to_task(result)
        return None

    async def update_priority(self, id: str, priority: TaskPriority) -> Task | None:
        """Actualiza la prioridad de una tarea."""
        notion_priority = self._map_priority_to_notion(priority)
        result = await self._notion.update_task_priority(id, notion_priority)
        if result:
            return self._notion_to_task(result)
        return None

    async def reschedule(self, id: str, new_date: date) -> Task | None:
        """Reprograma una tarea para otra fecha."""
        result = await self._notion.update_task_dates(
            task_id=id,
            fecha_do=new_date.isoformat(),
        )
        if result:
            return self._notion_to_task(result)
        return None

    async def complete(self, id: str) -> Task | None:
        """Marca una tarea como completada."""
        return await self.update_status(id, TaskStatus.DONE)

    # ==================== Aggregates ====================

    async def count_by_status(self) -> dict[TaskStatus, int]:
        """Cuenta tareas por estado."""
        pending = await self.get_pending(limit=500)
        counts: dict[TaskStatus, int] = {}
        for task in pending:
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts

    async def count_by_priority(self) -> dict[TaskPriority, int]:
        """Cuenta tareas por prioridad."""
        pending = await self.get_pending(limit=500)
        counts: dict[TaskPriority, int] = {}
        for task in pending:
            counts[task.priority] = counts.get(task.priority, 0) + 1
        return counts

    async def get_workload_summary(self) -> dict[str, Any]:
        """Obtiene resumen de carga de trabajo."""
        pending = await self.get_pending(limit=200)

        by_priority = {}
        by_status = {}
        overdue = 0
        for task in pending:
            by_priority[task.priority.value] = by_priority.get(task.priority.value, 0) + 1
            by_status[task.status.value] = by_status.get(task.status.value, 0) + 1
            if task.is_overdue:
                overdue += 1

        # Próximos deadlines
        upcoming_deadlines = sorted(
            [t for t in pending if t.due_date and t.days_until_due is not None and t.days_until_due >= 0],
            key=lambda t: t.due_date or date.max
        )[:5]

        return {
            "total_pending": len(pending),
            "overdue": overdue,
            "by_priority": by_priority,
            "by_status": by_status,
            "deadlines_this_week": [
                {"task": t.title, "date": t.due_date.isoformat() if t.due_date else None}
                for t in upcoming_deadlines
            ],
        }
