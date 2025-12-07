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
            description="Marca una tarea como completada.",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID de la tarea"}
                },
                "required": ["task_id"]
            },
            function=self._complete_task
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

        async with get_session() as session:
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
                # TODO: Habilitar embeddings después de arreglar migración
                # La columna embedding es double precision[] pero debe ser vector(768)
                embedding=None,
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
