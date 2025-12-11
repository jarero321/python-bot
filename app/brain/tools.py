"""
Tools para Carlos Brain.

Cada tool es una función que el Brain puede llamar.
El Brain decide qué tools usar basándose en el contexto.

Para agregar nuevas capacidades, solo agrega más tools aquí.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Coroutine
from uuid import UUID

from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Resultado de la ejecución de un tool."""
    success: bool
    data: Any = None
    message: str | None = None
    error: str | None = None


@dataclass
class Tool:
    """Definición de un tool."""
    name: str
    description: str
    parameters: dict  # JSON Schema de parámetros
    function: Callable[..., Coroutine[Any, Any, ToolResult]]


class ToolRegistry:
    """
    Registro de todos los tools disponibles para el Brain.

    Uso:
        registry = ToolRegistry(user_id)
        result = await registry.execute("get_tasks_for_today")
        result = await registry.execute("create_task", title="Mi tarea", priority="high")
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._tools: dict[str, Tool] = {}
        self._register_all_tools()

    def _register_all_tools(self) -> None:
        """Registra todos los tools disponibles."""
        # Tasks
        self._register_task_tools()
        # Projects
        self._register_project_tools()
        # Reminders
        self._register_reminder_tools()
        # Finance
        self._register_finance_tools()
        # Health
        self._register_health_tools()
        # User & Context
        self._register_user_tools()
        # Communication
        self._register_communication_tools()

    def get_tools_schema(self) -> list[dict]:
        """Retorna el schema de todos los tools para el LLM."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self._tools.values()
        ]

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Ejecuta un tool por nombre."""
        if tool_name not in self._tools:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' no encontrado"
            )

        tool = self._tools[tool_name]
        try:
            result = await tool.function(**kwargs)
            logger.info(f"Tool {tool_name} ejecutado: success={result.success}")
            return result
        except Exception as e:
            logger.exception(f"Error ejecutando tool {tool_name}")
            return ToolResult(success=False, error=str(e))

    # ==================== TASK TOOLS ====================

    def _register_task_tools(self) -> None:
        """Registra tools relacionados con tareas."""

        self._tools["get_tasks_for_today"] = Tool(
            name="get_tasks_for_today",
            description="Obtiene todas las tareas programadas para hoy, incluyendo las que están en progreso, vencen hoy, o están marcadas como 'today'.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_tasks_for_today
        )

        self._tools["get_overdue_tasks"] = Tool(
            name="get_overdue_tasks",
            description="Obtiene tareas vencidas (due_date pasado y no completadas).",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_overdue_tasks
        )

        self._tools["get_task_in_progress"] = Tool(
            name="get_task_in_progress",
            description="Obtiene la tarea actualmente en estado 'doing'.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_task_in_progress
        )

        self._tools["create_task"] = Tool(
            name="create_task",
            description="Crea una nueva tarea. El Brain debe inferir contexto, complejidad y prioridad si no se especifican.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Título de la tarea"},
                    "priority": {"type": "string", "enum": ["urgent", "high", "normal", "low"]},
                    "due_date": {"type": "string", "description": "Fecha límite (YYYY-MM-DD)"},
                    "context": {"type": "string", "description": "PayCash, Freelance, Personal, Estudio"},
                    "project_id": {"type": "string", "description": "UUID del proyecto"},
                    "complexity": {"type": "string", "enum": ["quick", "standard", "heavy", "epic"]},
                    "estimated_minutes": {"type": "integer"},
                    "notes": {"type": "string"},
                    "parent_task_id": {"type": "string", "description": "UUID de tarea padre (para subtareas)"},
                    "blocked_by_external": {"type": "string", "description": "Descripción del blocker externo"},
                },
                "required": ["title"]
            },
            function=self._create_task
        )

        self._tools["update_task_status"] = Tool(
            name="update_task_status",
            description="Actualiza el estado de una tarea.",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID de la tarea"},
                    "status": {"type": "string", "enum": ["backlog", "planned", "today", "doing", "paused", "done", "cancelled"]}
                },
                "required": ["task_id", "status"]
            },
            function=self._update_task_status
        )

        self._tools["complete_task"] = Tool(
            name="complete_task",
            description="Marca una tarea como completada usando su UUID.",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID de la tarea"}
                },
                "required": ["task_id"]
            },
            function=self._complete_task
        )

        self._tools["find_and_complete_task"] = Tool(
            name="find_and_complete_task",
            description="Busca una tarea por título y la marca como completada. Útil cuando el usuario dice 'termina la tarea X' sin dar el UUID.",
            parameters={
                "type": "object",
                "properties": {
                    "title_search": {"type": "string", "description": "Texto a buscar en el título de la tarea"}
                },
                "required": ["title_search"]
            },
            function=self._find_and_complete_task
        )

        self._tools["search_tasks"] = Tool(
            name="search_tasks",
            description="Busca tareas por texto, estado, contexto o proyecto.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto a buscar"},
                    "status": {"type": "string"},
                    "context": {"type": "string"},
                    "project_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": []
            },
            function=self._search_tasks
        )

        self._tools["get_blocked_tasks"] = Tool(
            name="get_blocked_tasks",
            description="Obtiene tareas que están bloqueadas.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_blocked_tasks
        )

        self._tools["unblock_task"] = Tool(
            name="unblock_task",
            description="Desbloquea una tarea.",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"}
                },
                "required": ["task_id"]
            },
            function=self._unblock_task
        )

    async def _get_tasks_for_today(self) -> ToolResult:
        """Obtiene tareas para hoy."""
        from app.db.models import TaskModel, ProjectModel

        async with get_session() as session:
            today = date.today()

            result = await session.execute(
                select(TaskModel, ProjectModel.name.label("project_name"))
                .outerjoin(ProjectModel, TaskModel.project_id == ProjectModel.id)
                .where(TaskModel.user_id == self.user_id)
                .where(
                    or_(
                        TaskModel.status == "today",
                        TaskModel.status == "doing",
                        and_(TaskModel.scheduled_date == today, TaskModel.status.notin_(["done", "cancelled"])),
                        and_(TaskModel.due_date == today, TaskModel.status.notin_(["done", "cancelled"]))
                    )
                )
                .order_by(
                    # Prioridad: urgent > high > normal > low
                    func.array_position(
                        ["urgent", "high", "normal", "low"],
                        TaskModel.priority
                    ),
                    TaskModel.due_date.nulls_last()
                )
            )

            tasks = []
            for row in result:
                task = row[0]
                project_name = row[1]
                tasks.append({
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status,
                    "priority": task.priority,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "context": task.context,
                    "project_name": project_name,
                    "complexity": task.complexity,
                    "estimated_minutes": task.estimated_minutes,
                    "is_blocked": task.blocked_by_task_id is not None or task.blocked_by_external is not None,
                    "blocked_by": task.blocked_by_external
                })

            return ToolResult(
                success=True,
                data=tasks,
                message=f"{len(tasks)} tareas para hoy"
            )

    async def _get_overdue_tasks(self) -> ToolResult:
        """Obtiene tareas vencidas."""
        from app.db.models import TaskModel

        async with get_session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.user_id == self.user_id)
                .where(TaskModel.due_date < date.today())
                .where(TaskModel.status.notin_(["done", "cancelled"]))
                .order_by(TaskModel.due_date)
            )

            tasks = [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "due_date": t.due_date.isoformat(),
                    "days_overdue": (date.today() - t.due_date).days,
                    "priority": t.priority,
                    "context": t.context
                }
                for t in result.scalars()
            ]

            return ToolResult(
                success=True,
                data=tasks,
                message=f"{len(tasks)} tareas vencidas"
            )

    async def _get_task_in_progress(self) -> ToolResult:
        """Obtiene la tarea en progreso."""
        from app.db.models import TaskModel

        async with get_session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.user_id == self.user_id)
                .where(TaskModel.status == "doing")
                .limit(1)
            )

            task = result.scalar_one_or_none()

            if task:
                return ToolResult(
                    success=True,
                    data={
                        "id": str(task.id),
                        "title": task.title,
                        "context": task.context,
                        "started_at": task.updated_at.isoformat() if task.updated_at else None
                    }
                )
            else:
                return ToolResult(
                    success=True,
                    data=None,
                    message="No hay tarea en progreso"
                )

    async def _create_task(
        self,
        title: str,
        priority: str = "normal",
        due_date: str | None = None,
        context: str | None = None,
        project_id: str | None = None,
        complexity: str | None = None,
        estimated_minutes: int | None = None,
        notes: str | None = None,
        parent_task_id: str | None = None,
        blocked_by_external: str | None = None,
    ) -> ToolResult:
        """Crea una nueva tarea."""
        from app.db.models import TaskModel
        from app.brain.embeddings import get_embedding

        async with get_session() as session:
            # Generar embedding para RAG (búsqueda semántica, duplicados)
            embedding = await get_embedding(title)

            task = TaskModel(
                user_id=self.user_id,
                title=title,
                status="today" if not blocked_by_external else "backlog",
                priority=priority,
                due_date=date.fromisoformat(due_date) if due_date else None,
                context=context,
                project_id=project_id,
                complexity=complexity,
                estimated_minutes=estimated_minutes,
                notes=notes,
                parent_task_id=parent_task_id,
                blocked_by_external=blocked_by_external,
                blocked_at=datetime.now() if blocked_by_external else None,
                embedding=embedding,
            )

            session.add(task)
            await session.commit()
            await session.refresh(task)

            return ToolResult(
                success=True,
                data={
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status,
                    "priority": task.priority,
                    "context": task.context,
                    "due_date": task.due_date.isoformat() if task.due_date else None
                },
                message=f"Tarea creada: {title}"
            )

    async def _update_task_status(self, task_id: str, status: str) -> ToolResult:
        """Actualiza el estado de una tarea."""
        from app.db.models import TaskModel

        async with get_session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.id == task_id)
                .where(TaskModel.user_id == self.user_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                return ToolResult(success=False, error="Tarea no encontrada")

            old_status = task.status
            task.status = status

            if status == "done":
                task.completed_at = datetime.now()

            await session.commit()

            return ToolResult(
                success=True,
                data={"id": task_id, "old_status": old_status, "new_status": status},
                message=f"Estado actualizado: {old_status} -> {status}"
            )

    async def _complete_task(self, task_id: str) -> ToolResult:
        """Completa una tarea."""
        return await self._update_task_status(task_id, "done")

    async def _find_and_complete_task(self, title_search: str) -> ToolResult:
        """Busca una tarea por título y la completa."""
        from app.db.models import TaskModel

        async with get_session() as session:
            # Buscar tareas activas que coincidan con el título
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.user_id == self.user_id)
                .where(TaskModel.title.ilike(f"%{title_search}%"))
                .where(TaskModel.status.notin_(["done", "cancelled"]))
                .order_by(TaskModel.updated_at.desc())
                .limit(5)
            )
            tasks = result.scalars().all()

            if not tasks:
                return ToolResult(
                    success=False,
                    error=f"No encontré tareas activas con '{title_search}'"
                )

            if len(tasks) == 1:
                # Una sola coincidencia, completarla
                task = tasks[0]
                task.status = "done"
                task.completed_at = datetime.now()
                await session.commit()

                return ToolResult(
                    success=True,
                    data={"id": str(task.id), "title": task.title},
                    message=f"Tarea completada: {task.title}"
                )
            else:
                # Múltiples coincidencias, pedir clarificación
                options = [{"id": str(t.id), "title": t.title, "status": t.status} for t in tasks]
                return ToolResult(
                    success=False,
                    data={"matches": options},
                    error=f"Encontré {len(tasks)} tareas que coinciden. ¿Cuál quieres completar?",
                    message="Múltiples coincidencias"
                )

    async def _search_tasks(
        self,
        query: str | None = None,
        status: str | None = None,
        context: str | None = None,
        project_id: str | None = None,
        limit: int = 10
    ) -> ToolResult:
        """Busca tareas."""
        from app.db.models import TaskModel

        async with get_session() as session:
            stmt = select(TaskModel).where(TaskModel.user_id == self.user_id)

            if query:
                stmt = stmt.where(TaskModel.title.ilike(f"%{query}%"))
            if status:
                stmt = stmt.where(TaskModel.status == status)
            if context:
                stmt = stmt.where(TaskModel.context == context)
            if project_id:
                stmt = stmt.where(TaskModel.project_id == project_id)

            stmt = stmt.limit(limit)

            result = await session.execute(stmt)

            tasks = [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "context": t.context
                }
                for t in result.scalars()
            ]

            return ToolResult(success=True, data=tasks)

    async def _get_blocked_tasks(self) -> ToolResult:
        """Obtiene tareas bloqueadas."""
        from app.db.models import TaskModel

        async with get_session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.user_id == self.user_id)
                .where(
                    or_(
                        TaskModel.blocked_by_task_id.isnot(None),
                        TaskModel.blocked_by_external.isnot(None)
                    )
                )
                .where(TaskModel.status.notin_(["done", "cancelled"]))
            )

            tasks = [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "blocked_by": t.blocked_by_external,
                    "blocked_since": t.blocked_at.isoformat() if t.blocked_at else None
                }
                for t in result.scalars()
            ]

            return ToolResult(success=True, data=tasks)

    async def _unblock_task(self, task_id: str) -> ToolResult:
        """Desbloquea una tarea."""
        from app.db.models import TaskModel

        async with get_session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.id == task_id)
                .where(TaskModel.user_id == self.user_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                return ToolResult(success=False, error="Tarea no encontrada")

            task.blocked_by_task_id = None
            task.blocked_by_external = None
            task.blocked_at = None
            task.status = "today"

            await session.commit()

            return ToolResult(
                success=True,
                data={"id": task_id, "title": task.title},
                message=f"Tarea desbloqueada: {task.title}"
            )

    # ==================== PROJECT TOOLS ====================

    def _register_project_tools(self) -> None:
        """Registra tools de proyectos."""

        self._tools["get_active_projects"] = Tool(
            name="get_active_projects",
            description="Obtiene proyectos activos.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_active_projects
        )

        self._tools["get_project_tasks"] = Tool(
            name="get_project_tasks",
            description="Obtiene tareas de un proyecto.",
            parameters={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"}
                },
                "required": ["project_id"]
            },
            function=self._get_project_tasks
        )

    async def _get_active_projects(self) -> ToolResult:
        """Obtiene proyectos activos."""
        from app.db.models import ProjectModel

        async with get_session() as session:
            result = await session.execute(
                select(ProjectModel)
                .where(ProjectModel.user_id == self.user_id)
                .where(ProjectModel.status.in_(["active", "planning"]))
                .order_by(ProjectModel.updated_at.desc())
            )

            projects = [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "status": p.status,
                    "type": p.type,
                    "progress": p.progress,
                    "context": p.context,
                    "target_date": p.target_date.isoformat() if p.target_date else None
                }
                for p in result.scalars()
            ]

            return ToolResult(success=True, data=projects)

    async def _get_project_tasks(self, project_id: str) -> ToolResult:
        """Obtiene tareas de un proyecto."""
        from app.db.models import TaskModel

        async with get_session() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.project_id == project_id)
                .where(TaskModel.user_id == self.user_id)
                .order_by(TaskModel.status, TaskModel.priority)
            )

            tasks = [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority
                }
                for t in result.scalars()
            ]

            return ToolResult(success=True, data=tasks)

    # ==================== REMINDER TOOLS ====================

    def _register_reminder_tools(self) -> None:
        """Registra tools de recordatorios."""

        self._tools["create_reminder"] = Tool(
            name="create_reminder",
            description="Crea un recordatorio para una fecha/hora específica.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "scheduled_at": {"type": "string", "description": "ISO datetime"},
                    "task_id": {"type": "string", "description": "UUID de tarea relacionada (opcional)"}
                },
                "required": ["message", "scheduled_at"]
            },
            function=self._create_reminder
        )

        self._tools["get_pending_reminders"] = Tool(
            name="get_pending_reminders",
            description="Obtiene recordatorios pendientes.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_pending_reminders
        )

        self._tools["snooze_reminder"] = Tool(
            name="snooze_reminder",
            description="Pospone un recordatorio.",
            parameters={
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string"},
                    "minutes": {"type": "integer", "default": 30}
                },
                "required": ["reminder_id"]
            },
            function=self._snooze_reminder
        )

    async def _create_reminder(
        self,
        message: str,
        scheduled_at: str,
        task_id: str | None = None
    ) -> ToolResult:
        """Crea un recordatorio."""
        from app.db.models import ReminderModel

        async with get_session() as session:
            reminder = ReminderModel(
                user_id=self.user_id,
                message=message,
                scheduled_at=datetime.fromisoformat(scheduled_at),
                task_id=task_id
            )
            session.add(reminder)
            await session.commit()

            return ToolResult(
                success=True,
                data={"id": str(reminder.id), "scheduled_at": scheduled_at},
                message=f"Recordatorio creado para {scheduled_at}"
            )

    async def _get_pending_reminders(self) -> ToolResult:
        """Obtiene recordatorios pendientes."""
        from app.db.models import ReminderModel

        async with get_session() as session:
            result = await session.execute(
                select(ReminderModel)
                .where(ReminderModel.user_id == self.user_id)
                .where(ReminderModel.status == "pending")
                .order_by(ReminderModel.scheduled_at)
            )

            reminders = [
                {
                    "id": str(r.id),
                    "message": r.message,
                    "scheduled_at": r.scheduled_at.isoformat(),
                    "task_id": str(r.task_id) if r.task_id else None
                }
                for r in result.scalars()
            ]

            return ToolResult(success=True, data=reminders)

    async def _snooze_reminder(self, reminder_id: str, minutes: int = 30) -> ToolResult:
        """Pospone un recordatorio."""
        from app.db.models import ReminderModel

        async with get_session() as session:
            result = await session.execute(
                select(ReminderModel)
                .where(ReminderModel.id == reminder_id)
            )
            reminder = result.scalar_one_or_none()

            if not reminder:
                return ToolResult(success=False, error="Recordatorio no encontrado")

            reminder.status = "snoozed"
            reminder.snoozed_until = datetime.now() + timedelta(minutes=minutes)
            reminder.snooze_count += 1

            await session.commit()

            return ToolResult(
                success=True,
                message=f"Recordatorio pospuesto {minutes} minutos"
            )

    # ==================== FINANCE TOOLS ====================

    def _register_finance_tools(self) -> None:
        """Registra tools financieros."""

        self._tools["log_expense"] = Tool(
            name="log_expense",
            description="Registra un gasto.",
            parameters={
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "expense_date": {"type": "string", "description": "YYYY-MM-DD, default hoy"}
                },
                "required": ["amount", "category"]
            },
            function=self._log_expense
        )

        self._tools["get_spending_summary"] = Tool(
            name="get_spending_summary",
            description="Obtiene resumen de gastos del período.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 30}
                },
                "required": []
            },
            function=self._get_spending_summary
        )

        self._tools["get_debt_status"] = Tool(
            name="get_debt_status",
            description="Obtiene estado de deudas activas.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_debt_status
        )

    async def _log_expense(
        self,
        amount: float,
        category: str,
        description: str | None = None,
        expense_date: str | None = None
    ) -> ToolResult:
        """Registra un gasto."""
        from app.db.models import TransactionModel

        async with get_session() as session:
            transaction = TransactionModel(
                user_id=self.user_id,
                amount=Decimal(str(amount)),
                type="expense",
                category=category,
                description=description,
                date=date.fromisoformat(expense_date) if expense_date else date.today()
            )
            session.add(transaction)
            await session.commit()

            return ToolResult(
                success=True,
                data={"amount": amount, "category": category},
                message=f"Gasto registrado: ${amount} en {category}"
            )

    async def _get_spending_summary(self, days: int = 30) -> ToolResult:
        """Obtiene resumen de gastos."""
        from app.db.models import TransactionModel

        async with get_session() as session:
            start_date = date.today() - timedelta(days=days)

            result = await session.execute(
                select(
                    TransactionModel.category,
                    func.sum(TransactionModel.amount).label("total")
                )
                .where(TransactionModel.user_id == self.user_id)
                .where(TransactionModel.type == "expense")
                .where(TransactionModel.date >= start_date)
                .group_by(TransactionModel.category)
            )

            by_category = {row[0]: float(row[1]) for row in result}
            total = sum(by_category.values())

            return ToolResult(
                success=True,
                data={
                    "period_days": days,
                    "total": total,
                    "by_category": by_category
                }
            )

    async def _get_debt_status(self) -> ToolResult:
        """Obtiene estado de deudas."""
        from app.db.models import DebtModel

        async with get_session() as session:
            result = await session.execute(
                select(DebtModel)
                .where(DebtModel.user_id == self.user_id)
                .where(DebtModel.status == "active")
            )

            debts = [
                {
                    "id": str(d.id),
                    "creditor": d.creditor,
                    "current_balance": float(d.current_balance),
                    "monthly_payment": float(d.monthly_payment) if d.monthly_payment else None,
                    "due_day": d.due_day
                }
                for d in result.scalars()
            ]

            total_debt = sum(d["current_balance"] for d in debts)

            return ToolResult(
                success=True,
                data={
                    "debts": debts,
                    "total_debt": total_debt,
                    "count": len(debts)
                }
            )

    # ==================== HEALTH TOOLS ====================

    def _register_health_tools(self) -> None:
        """Registra tools de salud."""

        self._tools["log_workout"] = Tool(
            name="log_workout",
            description="Registra un entrenamiento.",
            parameters={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["push", "pull", "legs", "cardio", "full_body"]},
                    "exercises": {"type": "array", "items": {"type": "object"}},
                    "feeling": {"type": "string", "enum": ["great", "good", "meh", "bad"]},
                    "duration_minutes": {"type": "integer"},
                    "notes": {"type": "string"}
                },
                "required": ["type"]
            },
            function=self._log_workout
        )

        self._tools["get_workout_history"] = Tool(
            name="get_workout_history",
            description="Obtiene historial de entrenamientos.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 7}
                },
                "required": []
            },
            function=self._get_workout_history
        )

        self._tools["log_meal"] = Tool(
            name="log_meal",
            description="Registra una comida.",
            parameters={
                "type": "object",
                "properties": {
                    "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
                    "description": {"type": "string"},
                    "calories_estimate": {"type": "integer"},
                    "protein_estimate": {"type": "integer"}
                },
                "required": ["meal_type", "description"]
            },
            function=self._log_meal
        )

        self._tools["check_gym_today"] = Tool(
            name="check_gym_today",
            description="Verifica si hoy es día de gym y si ya fue.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._check_gym_today
        )

        # Body Metrics Tools
        self._tools["log_body_metrics"] = Tool(
            name="log_body_metrics",
            description="Registra métricas corporales (peso, grasa, medidas).",
            parameters={
                "type": "object",
                "properties": {
                    "weight_kg": {"type": "number", "description": "Peso en kg"},
                    "body_fat_percentage": {"type": "number", "description": "% de grasa corporal"},
                    "muscle_mass_kg": {"type": "number", "description": "Masa muscular en kg"},
                    "waist_cm": {"type": "number", "description": "Cintura en cm"},
                    "notes": {"type": "string"}
                },
                "required": ["weight_kg"]
            },
            function=self._log_body_metrics
        )

        self._tools["get_weight_history"] = Tool(
            name="get_weight_history",
            description="Obtiene historial de peso y métricas corporales.",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 30}
                },
                "required": []
            },
            function=self._get_weight_history
        )

        self._tools["get_daily_nutrition_summary"] = Tool(
            name="get_daily_nutrition_summary",
            description="Obtiene resumen nutricional del día (comidas, calorías, proteína).",
            parameters={
                "type": "object",
                "properties": {
                    "target_date": {"type": "string", "description": "YYYY-MM-DD, default hoy"}
                },
                "required": []
            },
            function=self._get_daily_nutrition_summary
        )

        self._tools["set_fitness_goal"] = Tool(
            name="set_fitness_goal",
            description="Establece una meta de fitness (peso, grasa, etc).",
            parameters={
                "type": "object",
                "properties": {
                    "goal_type": {"type": "string", "enum": ["weight_loss", "muscle_gain", "maintenance"]},
                    "target_value": {"type": "number", "description": "Valor objetivo (ej: 75 kg)"},
                    "target_date": {"type": "string", "description": "YYYY-MM-DD fecha objetivo"},
                    "daily_calories": {"type": "integer"},
                    "daily_protein_g": {"type": "integer"}
                },
                "required": ["goal_type", "target_value"]
            },
            function=self._set_fitness_goal
        )

        self._tools["get_fitness_goal_progress"] = Tool(
            name="get_fitness_goal_progress",
            description="Obtiene progreso hacia la meta de fitness activa.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_fitness_goal_progress
        )

    async def _log_workout(
        self,
        type: str,
        exercises: list[dict] | None = None,
        feeling: str | None = None,
        duration_minutes: int | None = None,
        notes: str | None = None
    ) -> ToolResult:
        """Registra un entrenamiento."""
        from app.db.models import WorkoutModel

        async with get_session() as session:
            workout = WorkoutModel(
                user_id=self.user_id,
                type=type,
                exercises=exercises or [],
                feeling=feeling,
                duration_minutes=duration_minutes,
                notes=notes
            )
            session.add(workout)
            await session.commit()

            return ToolResult(
                success=True,
                data={"type": type, "date": date.today().isoformat()},
                message=f"Entrenamiento de {type} registrado"
            )

    async def _get_workout_history(self, days: int = 7) -> ToolResult:
        """Obtiene historial de entrenamientos."""
        from app.db.models import WorkoutModel

        async with get_session() as session:
            start_date = date.today() - timedelta(days=days)

            result = await session.execute(
                select(WorkoutModel)
                .where(WorkoutModel.user_id == self.user_id)
                .where(WorkoutModel.date >= start_date)
                .order_by(WorkoutModel.date.desc())
            )

            workouts = [
                {
                    "date": w.date.isoformat(),
                    "type": w.type,
                    "feeling": w.feeling,
                    "duration_minutes": w.duration_minutes
                }
                for w in result.scalars()
            ]

            return ToolResult(
                success=True,
                data={
                    "workouts": workouts,
                    "total_sessions": len(workouts),
                    "period_days": days
                }
            )

    async def _log_meal(
        self,
        meal_type: str,
        description: str,
        calories_estimate: int | None = None,
        protein_estimate: int | None = None
    ) -> ToolResult:
        """Registra una comida."""
        from app.db.models import NutritionLogModel

        async with get_session() as session:
            meal = NutritionLogModel(
                user_id=self.user_id,
                meal_type=meal_type,
                description=description,
                calories_estimate=calories_estimate,
                protein_estimate=protein_estimate
            )
            session.add(meal)
            await session.commit()

            return ToolResult(
                success=True,
                message=f"{meal_type} registrado"
            )

    async def _check_gym_today(self) -> ToolResult:
        """Verifica si hoy es día de gym."""
        from app.db.models import UserProfileModel, WorkoutModel

        async with get_session() as session:
            # Obtener preferencias
            profile_result = await session.execute(
                select(UserProfileModel)
                .where(UserProfileModel.id == self.user_id)
            )
            profile = profile_result.scalar_one_or_none()

            if not profile:
                return ToolResult(success=False, error="Perfil no encontrado")

            today_weekday = date.today().strftime("%a").lower()
            is_gym_day = today_weekday in (profile.gym_days or [])

            # Verificar si ya fue
            workout_result = await session.execute(
                select(WorkoutModel)
                .where(WorkoutModel.user_id == self.user_id)
                .where(WorkoutModel.date == date.today())
            )
            already_went = workout_result.scalar_one_or_none() is not None

            return ToolResult(
                success=True,
                data={
                    "is_gym_day": is_gym_day,
                    "already_went": already_went,
                    "gym_days": profile.gym_days
                }
            )

    async def _log_body_metrics(
        self,
        weight_kg: float,
        body_fat_percentage: float | None = None,
        muscle_mass_kg: float | None = None,
        waist_cm: float | None = None,
        notes: str | None = None
    ) -> ToolResult:
        """Registra métricas corporales."""
        from app.db.models import BodyMetricsModel, FitnessGoalModel

        async with get_session() as session:
            metrics = BodyMetricsModel(
                user_id=self.user_id,
                weight_kg=Decimal(str(weight_kg)),
                body_fat_percentage=Decimal(str(body_fat_percentage)) if body_fat_percentage else None,
                muscle_mass_kg=Decimal(str(muscle_mass_kg)) if muscle_mass_kg else None,
                waist_cm=Decimal(str(waist_cm)) if waist_cm else None,
                time_of_day="morning" if datetime.now().hour < 12 else "evening",
                notes=notes
            )
            session.add(metrics)

            # Actualizar meta activa si existe
            goal_result = await session.execute(
                select(FitnessGoalModel)
                .where(FitnessGoalModel.user_id == self.user_id)
                .where(FitnessGoalModel.status == "active")
                .order_by(FitnessGoalModel.created_at.desc())
                .limit(1)
            )
            goal = goal_result.scalar_one_or_none()
            if goal:
                goal.current_value = Decimal(str(weight_kg))

            await session.commit()

            # Obtener peso anterior para comparar
            prev_result = await session.execute(
                select(BodyMetricsModel)
                .where(BodyMetricsModel.user_id == self.user_id)
                .where(BodyMetricsModel.date < date.today())
                .order_by(BodyMetricsModel.date.desc())
                .limit(1)
            )
            prev = prev_result.scalar_one_or_none()

            diff = None
            if prev:
                diff = round(float(weight_kg) - float(prev.weight_kg), 2)

            return ToolResult(
                success=True,
                data={
                    "weight_kg": weight_kg,
                    "date": date.today().isoformat(),
                    "diff_from_previous": diff,
                    "previous_weight": float(prev.weight_kg) if prev else None
                },
                message=f"Peso registrado: {weight_kg} kg" + (f" ({'+' if diff > 0 else ''}{diff} kg)" if diff else "")
            )

    async def _get_weight_history(self, days: int = 30) -> ToolResult:
        """Obtiene historial de peso."""
        from app.db.models import BodyMetricsModel

        async with get_session() as session:
            start_date = date.today() - timedelta(days=days)

            result = await session.execute(
                select(BodyMetricsModel)
                .where(BodyMetricsModel.user_id == self.user_id)
                .where(BodyMetricsModel.date >= start_date)
                .order_by(BodyMetricsModel.date.desc())
            )

            entries = result.scalars().all()

            if not entries:
                return ToolResult(
                    success=True,
                    data={"entries": [], "count": 0},
                    message="No hay registros de peso en este período"
                )

            history = [
                {
                    "date": e.date.isoformat(),
                    "weight_kg": float(e.weight_kg),
                    "body_fat_percentage": float(e.body_fat_percentage) if e.body_fat_percentage else None,
                    "waist_cm": float(e.waist_cm) if e.waist_cm else None
                }
                for e in entries
            ]

            # Calcular estadísticas
            weights = [float(e.weight_kg) for e in entries]
            first_weight = weights[-1] if weights else None
            last_weight = weights[0] if weights else None
            total_change = round(last_weight - first_weight, 2) if first_weight and last_weight else None

            return ToolResult(
                success=True,
                data={
                    "entries": history,
                    "count": len(history),
                    "period_days": days,
                    "min_weight": min(weights) if weights else None,
                    "max_weight": max(weights) if weights else None,
                    "avg_weight": round(sum(weights) / len(weights), 2) if weights else None,
                    "total_change": total_change,
                    "current_weight": last_weight
                }
            )

    async def _get_daily_nutrition_summary(self, target_date: str | None = None) -> ToolResult:
        """Obtiene resumen nutricional del día."""
        from app.db.models import NutritionLogModel, FitnessGoalModel

        async with get_session() as session:
            check_date = date.fromisoformat(target_date) if target_date else date.today()

            result = await session.execute(
                select(NutritionLogModel)
                .where(NutritionLogModel.user_id == self.user_id)
                .where(NutritionLogModel.date == check_date)
                .order_by(NutritionLogModel.created_at)
            )

            meals = result.scalars().all()

            # Totales
            total_calories = sum(m.calories_estimate or 0 for m in meals)
            total_protein = sum(m.protein_estimate or 0 for m in meals)

            # Obtener metas si hay
            goal_result = await session.execute(
                select(FitnessGoalModel)
                .where(FitnessGoalModel.user_id == self.user_id)
                .where(FitnessGoalModel.status == "active")
                .limit(1)
            )
            goal = goal_result.scalar_one_or_none()

            meals_data = [
                {
                    "meal_type": m.meal_type,
                    "description": m.description,
                    "calories": m.calories_estimate,
                    "protein": m.protein_estimate,
                    "is_healthy": m.is_healthy
                }
                for m in meals
            ]

            return ToolResult(
                success=True,
                data={
                    "date": check_date.isoformat(),
                    "meals": meals_data,
                    "meal_count": len(meals),
                    "total_calories": total_calories,
                    "total_protein": total_protein,
                    "calorie_goal": goal.daily_calories if goal else None,
                    "protein_goal": goal.daily_protein_g if goal else None,
                    "calories_remaining": (goal.daily_calories - total_calories) if goal and goal.daily_calories else None,
                    "protein_remaining": (goal.daily_protein_g - total_protein) if goal and goal.daily_protein_g else None
                }
            )

    async def _set_fitness_goal(
        self,
        goal_type: str,
        target_value: float,
        target_date: str | None = None,
        daily_calories: int | None = None,
        daily_protein_g: int | None = None
    ) -> ToolResult:
        """Establece una meta de fitness."""
        from app.db.models import FitnessGoalModel, BodyMetricsModel

        async with get_session() as session:
            # Obtener peso actual
            weight_result = await session.execute(
                select(BodyMetricsModel)
                .where(BodyMetricsModel.user_id == self.user_id)
                .order_by(BodyMetricsModel.date.desc())
                .limit(1)
            )
            current = weight_result.scalar_one_or_none()
            start_value = float(current.weight_kg) if current else target_value

            # Desactivar metas anteriores
            await session.execute(
                update(FitnessGoalModel)
                .where(FitnessGoalModel.user_id == self.user_id)
                .where(FitnessGoalModel.status == "active")
                .values(status="abandoned")
            )

            goal = FitnessGoalModel(
                user_id=self.user_id,
                goal_type=goal_type,
                target_value=Decimal(str(target_value)),
                start_value=Decimal(str(start_value)),
                current_value=Decimal(str(start_value)),
                target_date=date.fromisoformat(target_date) if target_date else None,
                daily_calories=daily_calories,
                daily_protein_g=daily_protein_g,
                status="active"
            )
            session.add(goal)
            await session.commit()

            diff_to_goal = round(target_value - start_value, 2)

            return ToolResult(
                success=True,
                data={
                    "goal_type": goal_type,
                    "start_value": start_value,
                    "target_value": target_value,
                    "diff_to_goal": diff_to_goal,
                    "target_date": target_date,
                    "daily_calories": daily_calories,
                    "daily_protein_g": daily_protein_g
                },
                message=f"Meta establecida: {goal_type} → {target_value} kg ({'+' if diff_to_goal > 0 else ''}{diff_to_goal} kg)"
            )

    async def _get_fitness_goal_progress(self) -> ToolResult:
        """Obtiene progreso hacia la meta activa."""
        from app.db.models import FitnessGoalModel, BodyMetricsModel

        async with get_session() as session:
            goal_result = await session.execute(
                select(FitnessGoalModel)
                .where(FitnessGoalModel.user_id == self.user_id)
                .where(FitnessGoalModel.status == "active")
                .order_by(FitnessGoalModel.created_at.desc())
                .limit(1)
            )
            goal = goal_result.scalar_one_or_none()

            if not goal:
                return ToolResult(
                    success=True,
                    data=None,
                    message="No hay meta de fitness activa"
                )

            # Obtener peso actual
            weight_result = await session.execute(
                select(BodyMetricsModel)
                .where(BodyMetricsModel.user_id == self.user_id)
                .order_by(BodyMetricsModel.date.desc())
                .limit(1)
            )
            current = weight_result.scalar_one_or_none()
            current_weight = float(current.weight_kg) if current else float(goal.start_value)

            # Calcular progreso
            start = float(goal.start_value)
            target = float(goal.target_value)
            total_diff = target - start
            current_diff = current_weight - start

            if total_diff != 0:
                progress_pct = round((current_diff / total_diff) * 100, 1)
            else:
                progress_pct = 100 if current_weight == target else 0

            remaining = round(target - current_weight, 2)

            # Días restantes
            days_remaining = None
            if goal.target_date:
                days_remaining = (goal.target_date - date.today()).days

            return ToolResult(
                success=True,
                data={
                    "goal_type": goal.goal_type,
                    "start_value": start,
                    "target_value": target,
                    "current_value": current_weight,
                    "progress_percentage": max(0, min(100, progress_pct)),
                    "remaining_to_goal": remaining,
                    "target_date": goal.target_date.isoformat() if goal.target_date else None,
                    "days_remaining": days_remaining,
                    "daily_calories": goal.daily_calories,
                    "daily_protein_g": goal.daily_protein_g,
                    "started_at": goal.start_date.isoformat()
                }
            )

    # ==================== USER TOOLS ====================

    def _register_user_tools(self) -> None:
        """Registra tools de usuario y contexto."""

        self._tools["get_user_profile"] = Tool(
            name="get_user_profile",
            description="Obtiene el perfil y preferencias del usuario.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_user_profile
        )

        self._tools["get_current_context"] = Tool(
            name="get_current_context",
            description="Obtiene el contexto actual: hora, día, si es horario laboral, etc.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=self._get_current_context
        )

    async def _get_user_profile(self) -> ToolResult:
        """Obtiene el perfil del usuario."""
        from app.db.models import UserProfileModel

        async with get_session() as session:
            result = await session.execute(
                select(UserProfileModel)
                .where(UserProfileModel.id == self.user_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                return ToolResult(success=False, error="Perfil no encontrado")

            return ToolResult(
                success=True,
                data={
                    "name": profile.name,
                    "work_start": profile.work_start.isoformat() if profile.work_start else None,
                    "work_end": profile.work_end.isoformat() if profile.work_end else None,
                    "work_days": profile.work_days,
                    "gym_days": profile.gym_days,
                    "contexts": profile.contexts,
                    "default_context": profile.default_context,
                    "timezone": profile.timezone
                }
            )

    async def _get_current_context(self) -> ToolResult:
        """Obtiene el contexto actual."""
        from app.db.models import UserProfileModel
        import pytz

        async with get_session() as session:
            result = await session.execute(
                select(UserProfileModel)
                .where(UserProfileModel.id == self.user_id)
            )
            profile = result.scalar_one_or_none()

            tz = pytz.timezone(profile.timezone if profile else "America/Mexico_City")
            now = datetime.now(tz)

            # Determinar si es horario laboral
            is_work_hours = False
            if profile and profile.work_start and profile.work_end:
                current_time = now.time()
                is_work_hours = profile.work_start <= current_time <= profile.work_end

            is_work_day = now.strftime("%a").lower() in (profile.work_days if profile else [])

            return ToolResult(
                success=True,
                data={
                    "current_time": now.strftime("%H:%M"),
                    "current_date": now.strftime("%Y-%m-%d"),
                    "day_of_week": now.strftime("%A"),
                    "day_of_week_short": now.strftime("%a").lower(),
                    "is_work_day": is_work_day,
                    "is_work_hours": is_work_hours and is_work_day,
                    "is_morning": 6 <= now.hour < 12,
                    "is_afternoon": 12 <= now.hour < 18,
                    "is_evening": 18 <= now.hour < 22,
                    "is_night": now.hour >= 22 or now.hour < 6
                }
            )

    # ==================== COMMUNICATION TOOLS ====================

    def _register_communication_tools(self) -> None:
        """Registra tools de comunicación."""

        self._tools["send_message"] = Tool(
            name="send_message",
            description="Envía un mensaje al usuario por Telegram.",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "keyboard": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "object"}
                        },
                        "description": "Botones inline [[{text, callback_data}]]"
                    },
                    "parse_mode": {"type": "string", "default": "HTML"}
                },
                "required": ["text"]
            },
            function=self._send_message
        )

    async def _send_message(
        self,
        text: str,
        keyboard: list[list[dict]] | None = None,
        parse_mode: str = "HTML"
    ) -> ToolResult:
        """Envia un mensaje por Telegram."""
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
        from app.config import get_settings

        settings = get_settings()
        bot = Bot(token=settings.telegram_bot_token)

        # Construir keyboard si hay
        reply_markup = None
        if keyboard:
            buttons = [
                [
                    InlineKeyboardButton(
                        text=btn.get("text", ""),
                        callback_data=btn.get("callback_data", "")
                    )
                    for btn in row
                ]
                for row in keyboard
            ]
            reply_markup = InlineKeyboardMarkup(buttons)

        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )

        return ToolResult(
            success=True,
            message="Mensaje enviado"
        )
