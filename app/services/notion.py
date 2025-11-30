"""Servicio de Notion para interactuar con la API.

IMPORTANTE: Los nombres de campos corresponden EXACTAMENTE a los definidos
en Documentacion.MD - NO modificar sin actualizar el schema.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from notion_client import AsyncClient
from notion_client.errors import APIResponseError

from app.config import get_settings
from app.utils.cache import get_cache, NotionCacheKeys, cached
from app.utils.errors import NotionAPIError, retry_notion, log_error, ErrorCategory

logger = logging.getLogger(__name__)
settings = get_settings()


class NotionDatabase:
    """IDs de las bases de datos de Notion."""

    INBOX = "6a4c92f0fa26438186a51b456b6ac63c"
    TASKS = "bbfd07401cb146e286132fb36dd22501"
    PROJECTS = "00ddf18ff47d44999d2f8587b248500f"
    KNOWLEDGE = "66367a534704483fac8ddd5256759f26"
    NUTRITION = "56325465fd88435aa98ec6230735e567"
    WORKOUTS = "8f2df8b8b657489498cf22fced671de1"
    TRANSACTIONS = "5dc7d2d251e94bd1ae38095a853c74b7"
    DEBTS = "c7d0902e9cf04a339aaea353ec2cd803"


# ==================== ENUMS EXACTOS DE NOTION ====================


class TaskEstado(str, Enum):
    """Estados de tarea - EXACTOS de Notion."""

    BACKLOG = "📥 Backlog"
    PLANNED = "📋 Planned"
    TODAY = "🎯 Today"
    DOING = "⚡ Doing"
    PAUSED = "⏸️ Paused"
    DONE = "✅ Done"
    CANCELLED = "❌ Cancelled"


class TaskPrioridad(str, Enum):
    """Prioridades de tarea - EXACTOS de Notion."""

    URGENTE = "🔥 Urgente"
    ALTA = "⚡ Alta"
    NORMAL = "🔄 Normal"
    BAJA = "🧊 Baja"


class TaskComplejidad(str, Enum):
    """Complejidad de tarea - EXACTOS de Notion."""

    QUICK = "🟢 Quick (<30m)"
    STANDARD = "🟡 Standard (30m-2h)"
    HEAVY = "🔴 Heavy (2-4h)"
    EPIC = "⚫ Epic (4h+)"


class TaskEnergia(str, Enum):
    """Energía requerida - EXACTOS de Notion."""

    DEEP_WORK = "🧠 Deep Work"
    MEDIUM = "💪 Medium"
    LOW = "😴 Low"


class TaskBloque(str, Enum):
    """Bloques de tiempo - EXACTOS de Notion."""

    MORNING = "🌅 Morning"
    AFTERNOON = "☀️ Afternoon"
    EVENING = "🌆 Evening"


class TaskContexto(str, Enum):
    """Contextos de trabajo - EXACTOS de Notion."""

    PAYCASH = "PayCash"
    FREELANCE_PA = "Freelance-PA"
    FREELANCE_GOOGLE = "Freelance-Google"
    PERSONAL = "Personal"
    WORKANA = "Workana"
    ESTUDIO = "Estudio"


class ProjectTipo(str, Enum):
    """Tipos de proyecto - EXACTOS de Notion."""

    TRABAJO = "💼 Trabajo"
    FREELANCE = "💰 Freelance"
    APRENDIZAJE = "📚 Aprendizaje"
    SIDE_PROJECT = "🚀 Side Project"
    PERSONAL = "🏠 Personal"
    HOBBY = "🎯 Hobby"
    FINANCIERO = "💳 Financiero"
    BUSQUEDA = "🔍 Búsqueda"


class ProjectEstado(str, Enum):
    """Estados de proyecto - EXACTOS de Notion."""

    IDEA = "💡 Idea"
    PLANNING = "📝 Planning"
    ACTIVO = "🟢 Activo"
    ESPERANDO = "🟡 Esperando"
    PAUSADO = "⏸️ Pausado"
    COMPLETADO = "✅ Completado"
    CANCELADO = "❌ Cancelado"


class WorkoutTipo(str, Enum):
    """Tipos de workout - EXACTOS de Notion."""

    PUSH = "Push"
    PULL = "Pull"
    LEGS = "Legs"
    CARDIO = "Cardio"
    REST = "Rest"


class WorkoutSensacion(str, Enum):
    """Sensación del workout - EXACTOS de Notion."""

    FUERTE = "💪 Fuerte"
    NORMAL = "😅 Normal"
    PESADO = "😓 Pesado"
    MOLESTIA = "🤕 Molestia"


class NutritionCategoria(str, Enum):
    """Categoría de comida - EXACTOS de Notion."""

    SALUDABLE = "🟢 Saludable"
    MODERADO = "🟡 Moderado"
    PESADO = "🔴 Pesado"


class NutritionEvaluacion(str, Enum):
    """Evaluación del día - EXACTOS de Notion."""

    BUEN_DIA = "🟢 Buen día"
    REGULAR = "🟡 Regular"
    MEJORABLE = "🔴 Mejorable"


class TransactionTipo(str, Enum):
    """Tipos de transacción - EXACTOS de Notion."""

    INGRESO = "💵 Ingreso"
    GASTO_FIJO = "🏠 Gasto Fijo"
    GASTO_VARIABLE = "🛒 Gasto Variable"
    PAGO_DEUDA = "💳 Pago Deuda"
    AHORRO = "💰 Ahorro"


class TransactionCategoria(str, Enum):
    """Categorías de transacción - EXACTOS de Notion."""

    SALARIO = "Salario"
    FREELANCE = "Freelance"
    RENTA = "Renta"
    SERVICIOS = "Servicios"
    COMIDA = "Comida"
    TECH = "Tech"
    ENTRETENIMIENTO = "Entretenimiento"
    TRANSPORTE = "Transporte"
    DEUDA = "Deuda"
    OTRO = "Otro"


class DebtEstado(str, Enum):
    """Estados de deuda - EXACTOS de Notion."""

    ACTIVA = "🔴 Activa"
    NEGOCIANDO = "🟡 Negociando"
    LIQUIDADA = "✅ Liquidada"


class DebtAcreedor(str, Enum):
    """Tipos de acreedor - EXACTOS de Notion."""

    BANCO = "Banco"
    TIENDA = "Tienda"
    PERSONA = "Persona"
    OTRO = "Otro"


class InboxFuente(str, Enum):
    """Fuentes del inbox - EXACTOS de Notion."""

    TELEGRAM = "Telegram"
    MANUAL = "Manual"
    VOZ = "Voz"


class KnowledgeTipo(str, Enum):
    """Tipos de conocimiento - EXACTOS de Notion."""

    NOTA = "📝 Nota"
    IDEA = "💡 Idea"
    ARTICULO = "📰 Artículo"
    VIDEO = "🎥 Video"
    LIBRO = "📚 Libro"
    CODIGO = "💻 Código"
    SOLUCION = "🔧 Solución"


class NotionService:
    """Cliente para interactuar con Notion API."""

    def __init__(self):
        self.client = AsyncClient(auth=settings.notion_api_key)

    # ==================== INBOX ====================
    # Campos: Contenido (Title), Fuente (Select), Fecha (Date),
    #         Procesado (Checkbox), Confianza AI (Number),
    #         Proyecto Sugerido (Relation), Notas (Text)

    async def create_inbox_item(
        self,
        contenido: str,
        fuente: InboxFuente = InboxFuente.TELEGRAM,
        notas: str | None = None,
        confianza_ai: float | None = None,
        proyecto_sugerido_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Crea un item en el Inbox."""
        try:
            properties = {
                "Contenido": {"title": [{"text": {"content": contenido}}]},
                "Fuente": {"select": {"name": fuente.value}},
                "Fecha": {"date": {"start": datetime.now().isoformat()}},
                "Procesado": {"checkbox": False},
            }

            if confianza_ai is not None:
                properties["Confianza AI"] = {"number": int(confianza_ai * 100)}

            if proyecto_sugerido_id:
                properties["Proyecto Sugerido"] = {
                    "relation": [{"id": proyecto_sugerido_id}]
                }

            if notas:
                properties["Notas"] = {
                    "rich_text": [{"text": {"content": notas}}]
                }

            response = await self.client.pages.create(
                parent={"database_id": NotionDatabase.INBOX},
                properties=properties,
            )
            logger.info(f"Inbox item creado: {contenido}")
            return response
        except APIResponseError as e:
            logger.error(f"Error creando inbox item: {e}")
            return None

    async def get_inbox_items(
        self, solo_sin_procesar: bool = True, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Obtiene items del Inbox."""
        try:
            filter_config = None
            if solo_sin_procesar:
                filter_config = {"property": "Procesado", "checkbox": {"equals": False}}

            response = await self.client.databases.query(
                database_id=NotionDatabase.INBOX,
                filter=filter_config,
                page_size=limit,
                sorts=[{"property": "Fecha", "direction": "descending"}],
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo inbox: {e}")
            return []

    async def mark_inbox_processed(
        self, page_id: str, procesado: bool = True
    ) -> dict[str, Any] | None:
        """Marca un item del inbox como procesado."""
        try:
            response = await self.client.pages.update(
                page_id=page_id,
                properties={"Procesado": {"checkbox": procesado}},
            )
            logger.info(f"Inbox {page_id} marcado como procesado: {procesado}")
            return response
        except APIResponseError as e:
            logger.error(f"Error marcando inbox como procesado: {e}")
            return None

    # ==================== TASKS ====================
    # Campos: Tarea (Title), Proyecto (Relation), Contexto (Select),
    #         Estado (Select), Prioridad (Select), Complejidad (Select),
    #         Energía (Select), Tiempo Est. (Select), Tiempo Real (Number),
    #         Bloque (Select), Daily Slot (Select), Fecha Do (Date),
    #         Fecha Due (Date), Fecha Done (Date), En Jira (Checkbox),
    #         Bloqueada (Checkbox), Blocker (Text), Recordatorio (Date),
    #         From Inbox (Relation), Subtareas (Relation), Notas (Text)

    async def create_task(
        self,
        tarea: str,
        contexto: TaskContexto = TaskContexto.PERSONAL,
        estado: TaskEstado = TaskEstado.BACKLOG,
        prioridad: TaskPrioridad | None = None,
        complejidad: TaskComplejidad | None = None,
        energia: TaskEnergia | None = None,
        tiempo_est: str | None = None,
        bloque: TaskBloque | None = None,
        fecha_do: str | None = None,
        fecha_due: str | None = None,
        proyecto_id: str | None = None,
        from_inbox_id: str | None = None,
        parent_task_id: str | None = None,
        subtask_ids: list[str] | None = None,
        notas: str | None = None,
    ) -> dict[str, Any] | None:
        """Crea una tarea en la base de datos de Tasks."""
        try:
            properties = {
                "Tarea": {"title": [{"text": {"content": tarea}}]},
                "Contexto": {"select": {"name": contexto.value}},
                "Estado": {"select": {"name": estado.value}},
            }

            if prioridad:
                properties["Prioridad"] = {"select": {"name": prioridad.value}}

            if complejidad:
                properties["Complejidad"] = {"select": {"name": complejidad.value}}

            if energia:
                properties["Energia"] = {"select": {"name": energia.value}}

            if tiempo_est:
                properties["Tiempo Est"] = {"select": {"name": tiempo_est}}

            if bloque:
                properties["Bloque"] = {"select": {"name": bloque.value}}

            if fecha_do:
                properties["Fecha Do"] = {"date": {"start": fecha_do}}

            if fecha_due:
                properties["Fecha Due"] = {"date": {"start": fecha_due}}

            if proyecto_id:
                properties["Proyecto"] = {"relation": [{"id": proyecto_id}]}

            if from_inbox_id:
                properties["From Inbox"] = {"relation": [{"id": from_inbox_id}]}

            # Relación Subtareas (self-relation a Tasks)
            if subtask_ids:
                properties["Subtareas"] = {
                    "relation": [{"id": sid} for sid in subtask_ids]
                }

            if notas:
                properties["Notas"] = {"rich_text": [{"text": {"content": notas}}]}

            response = await self.client.pages.create(
                parent={"database_id": NotionDatabase.TASKS},
                properties=properties,
            )
            logger.info(f"Tarea creada: {tarea}")

            # Si se especificó parent_task_id, vincular esta tarea como subtarea del padre
            if parent_task_id and response:
                await self.add_subtask_to_parent(parent_task_id, response["id"])

            return response
        except APIResponseError as e:
            logger.error(f"Error creando tarea: {e}")
            return None

    async def get_tasks_for_today(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Obtiene tareas para hoy (Estado = Today o Doing)."""
        cache = get_cache()
        cache_key = NotionCacheKeys.TASKS_TODAY

        # Intentar obtener del cache
        if use_cache:
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        try:
            response = await self.client.databases.query(
                database_id=NotionDatabase.TASKS,
                filter={
                    "or": [
                        {"property": "Estado", "select": {"equals": TaskEstado.TODAY.value}},
                        {"property": "Estado", "select": {"equals": TaskEstado.DOING.value}},
                    ]
                },
                sorts=[{"property": "Prioridad", "direction": "ascending"}],
            )
            result = response.get("results", [])

            # Guardar en cache (TTL: 2 minutos para tareas activas)
            await cache.set(cache_key, result, ttl=120)

            return result
        except APIResponseError as e:
            log_error(e, "get_tasks_for_today", ErrorCategory.API_NOTION)
            return []

    async def get_pending_tasks(
        self,
        contexto: TaskContexto | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Obtiene tareas pendientes (no Done ni Cancelled)."""
        try:
            filter_conditions = [
                {"property": "Estado", "select": {"does_not_equal": TaskEstado.DONE.value}},
                {"property": "Estado", "select": {"does_not_equal": TaskEstado.CANCELLED.value}},
            ]

            if contexto:
                filter_conditions.append(
                    {"property": "Contexto", "select": {"equals": contexto.value}}
                )

            response = await self.client.databases.query(
                database_id=NotionDatabase.TASKS,
                filter={"and": filter_conditions},
                page_size=limit,
                sorts=[
                    {"property": "Prioridad", "direction": "ascending"},
                    {"property": "Fecha Due", "direction": "ascending"},
                ],
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo tareas pendientes: {e}")
            return []

    async def get_tasks_by_estado(
        self, estado: TaskEstado, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Obtiene tareas por estado específico."""
        try:
            response = await self.client.databases.query(
                database_id=NotionDatabase.TASKS,
                filter={"property": "Estado", "select": {"equals": estado.value}},
                page_size=limit,
                sorts=[{"property": "Prioridad", "direction": "ascending"}],
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo tareas por estado: {e}")
            return []

    async def update_task_estado(
        self,
        page_id: str,
        estado: TaskEstado,
        tiempo_real: int | None = None,
    ) -> dict[str, Any] | None:
        """Actualiza el estado de una tarea."""
        try:
            properties = {"Estado": {"select": {"name": estado.value}}}

            if tiempo_real is not None:
                properties["Tiempo Real"] = {"number": tiempo_real}

            # Si se completa, agregar fecha
            if estado == TaskEstado.DONE:
                properties["Fecha Done"] = {
                    "date": {"start": datetime.now().strftime("%Y-%m-%d")}
                }

            response = await self.client.pages.update(
                page_id=page_id,
                properties=properties,
            )
            logger.info(f"Tarea {page_id} actualizada a {estado.value}")

            # Invalidar cache de tareas
            await self.invalidate_tasks_cache()

            return response
        except APIResponseError as e:
            log_error(e, "update_task_estado", ErrorCategory.API_NOTION)
            return None

    async def add_subtask_to_parent(
        self, parent_task_id: str, subtask_id: str
    ) -> dict[str, Any] | None:
        """
        Agrega una subtarea a una tarea padre.

        Args:
            parent_task_id: ID de la tarea padre
            subtask_id: ID de la subtarea a agregar
        """
        try:
            # Primero obtener las subtareas actuales
            parent = await self.get_page(parent_task_id)
            if not parent:
                return None

            current_subtasks = parent.get("properties", {}).get("Subtareas", {}).get("relation", [])
            subtask_ids = [s["id"] for s in current_subtasks]

            # Agregar la nueva si no existe
            if subtask_id not in subtask_ids:
                subtask_ids.append(subtask_id)

            response = await self.client.pages.update(
                page_id=parent_task_id,
                properties={
                    "Subtareas": {"relation": [{"id": sid} for sid in subtask_ids]}
                },
            )
            logger.info(f"Subtarea {subtask_id} agregada a tarea {parent_task_id}")
            return response
        except APIResponseError as e:
            logger.error(f"Error agregando subtarea: {e}")
            return None

    async def get_subtasks(self, task_id: str) -> list[dict[str, Any]]:
        """
        Obtiene las subtareas de una tarea.

        Args:
            task_id: ID de la tarea padre
        """
        try:
            task = await self.get_page(task_id)
            if not task:
                return []

            subtask_relations = task.get("properties", {}).get("Subtareas", {}).get("relation", [])
            subtasks = []

            for rel in subtask_relations:
                subtask = await self.get_page(rel["id"])
                if subtask:
                    subtasks.append(subtask)

            return subtasks
        except APIResponseError as e:
            logger.error(f"Error obteniendo subtareas: {e}")
            return []

    async def set_task_blocker(
        self, page_id: str, blocker: str | None
    ) -> dict[str, Any] | None:
        """Establece o quita un blocker de una tarea."""
        try:
            properties = {
                "Bloqueada": {"checkbox": blocker is not None},
            }
            if blocker:
                properties["Blocker"] = {"rich_text": [{"text": {"content": blocker}}]}
            else:
                properties["Blocker"] = {"rich_text": []}

            response = await self.client.pages.update(
                page_id=page_id,
                properties=properties,
            )
            logger.info(f"Tarea {page_id} blocker: {blocker}")
            return response
        except APIResponseError as e:
            logger.error(f"Error actualizando blocker: {e}")
            return None

    async def update_task_priority(
        self, page_id: str, priority: TaskPrioridad
    ) -> dict[str, Any] | None:
        """Actualiza la prioridad de una tarea."""
        try:
            response = await self.client.pages.update(
                page_id=page_id,
                properties={
                    "Prioridad": {"select": {"name": priority.value}},
                },
            )
            logger.info(f"Tarea {page_id} prioridad: {priority.value}")
            await self.invalidate_tasks_cache()
            return response
        except APIResponseError as e:
            logger.error(f"Error actualizando prioridad: {e}")
            return None

    async def update_task_dates(
        self,
        page_id: str,
        fecha_do: str | None = None,
        fecha_due: str | None = None,
    ) -> dict[str, Any] | None:
        """Actualiza las fechas de una tarea."""
        try:
            properties = {}

            if fecha_do:
                properties["Fecha Do"] = {"date": {"start": fecha_do}}
            if fecha_due:
                properties["Fecha Due"] = {"date": {"start": fecha_due}}

            if not properties:
                return None

            response = await self.client.pages.update(
                page_id=page_id,
                properties=properties,
            )
            logger.info(f"Tarea {page_id} fechas actualizadas")
            await self.invalidate_tasks_cache()
            return response
        except APIResponseError as e:
            logger.error(f"Error actualizando fechas: {e}")
            return None

    # ==================== PROJECTS ====================
    # Campos: Proyecto (Title), Tipo (Select), Estado (Select),
    #         Objetivo (Text), Hito Actual (Text), Progreso Hito (Number),
    #         Genera Dinero (Checkbox), Ingreso Potencial (Number),
    #         Genera Bienestar (Multi-select), Costo (Number), Cliente (Text),
    #         Deadline (Date), Última Actividad (Date), Días Sin Actividad (Formula),
    #         En Rotación Estudio (Checkbox), Prioridad Financiera (Number),
    #         Tasks (Relation), Transactions (Relation), Notas (Text)

    async def get_projects(
        self,
        active_only: bool = True,
        tipo: ProjectTipo | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Obtiene la lista de proyectos."""
        cache = get_cache()
        cache_key = f"{NotionCacheKeys.PROJECTS_ACTIVE}:{tipo.value if tipo else 'all'}"

        if use_cache and active_only:
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        try:
            filter_conditions = []

            if active_only:
                filter_conditions.append(
                    {"property": "Estado", "select": {"equals": ProjectEstado.ACTIVO.value}}
                )

            if tipo:
                filter_conditions.append(
                    {"property": "Tipo", "select": {"equals": tipo.value}}
                )

            filter_config = None
            if filter_conditions:
                if len(filter_conditions) == 1:
                    filter_config = filter_conditions[0]
                else:
                    filter_config = {"and": filter_conditions}

            response = await self.client.databases.query(
                database_id=NotionDatabase.PROJECTS,
                filter=filter_config,
                sorts=[{"property": "Proyecto", "direction": "ascending"}],
            )
            result = response.get("results", [])

            # Cache proyectos activos por 5 minutos
            if active_only:
                await cache.set(cache_key, result, ttl=300)

            return result
        except APIResponseError as e:
            log_error(e, "get_projects", ErrorCategory.API_NOTION)
            return []

    async def create_project(
        self,
        nombre: str,
        tipo: ProjectTipo,
        estado: ProjectEstado = ProjectEstado.ACTIVO,
        objetivo: str | None = None,
        genera_dinero: bool = False,
        ingreso_potencial: float | None = None,
        costo: float | None = None,
        cliente: str | None = None,
        deadline: str | None = None,
        en_rotacion_estudio: bool = False,
        notas: str | None = None,
    ) -> dict[str, Any] | None:
        """Crea un nuevo proyecto."""
        try:
            # Propiedades básicas requeridas
            properties = {
                "Proyecto": {"title": [{"text": {"content": nombre}}]},
                "Tipo": {"select": {"name": tipo.value}},
                "Estado": {"select": {"name": estado.value}},
            }

            # Propiedades opcionales - solo agregar si existen en la DB
            # Estas se agregan con try/except individual para manejar si no existen
            optional_properties = {
                "Genera Dinero": {"checkbox": genera_dinero},
            }

            # Solo agregar "En Rotacion Estudio" si es True (para proyectos de estudio)
            # Nota: Sin tilde porque así está en Notion
            if en_rotacion_estudio:
                optional_properties["En Rotacion Estudio"] = {"checkbox": en_rotacion_estudio}

            if objetivo:
                optional_properties["Objetivo"] = {"rich_text": [{"text": {"content": objetivo}}]}

            if ingreso_potencial is not None:
                optional_properties["Ingreso Potencial"] = {"number": ingreso_potencial}

            if costo is not None:
                optional_properties["Costo"] = {"number": costo}

            if cliente:
                optional_properties["Cliente"] = {"rich_text": [{"text": {"content": cliente}}]}

            if deadline:
                optional_properties["Deadline"] = {"date": {"start": deadline}}

            if notas:
                optional_properties["Notas"] = {"rich_text": [{"text": {"content": notas}}]}

            # Intentar crear con todas las propiedades primero
            all_properties = {**properties, **optional_properties}

            try:
                response = await self.client.pages.create(
                    parent={"database_id": NotionDatabase.PROJECTS},
                    properties=all_properties,
                )
                logger.info(f"Proyecto creado: {nombre}")
                return response
            except APIResponseError as first_error:
                # Si falla por propiedad no existente, intentar solo con las básicas
                error_msg = str(first_error)
                if "is not a property that exists" in error_msg:
                    logger.warning(f"Propiedad opcional no existe, creando con propiedades básicas: {error_msg}")
                    response = await self.client.pages.create(
                        parent={"database_id": NotionDatabase.PROJECTS},
                        properties=properties,
                    )
                    logger.info(f"Proyecto creado (básico): {nombre}")
                    return response
                else:
                    raise first_error

        except APIResponseError as e:
            logger.error(f"Error creando proyecto: {e}")
            return None

    async def update_project_status(
        self,
        page_id: str,
        estado: ProjectEstado,
    ) -> bool:
        """Actualiza el estado de un proyecto."""
        try:
            await self.client.pages.update(
                page_id=page_id,
                properties={
                    "Estado": {"select": {"name": estado.value}},
                },
            )
            logger.info(f"Proyecto {page_id} actualizado a {estado.value}")
            await self.invalidate_projects_cache()
            return True
        except APIResponseError as e:
            logger.error(f"Error actualizando proyecto: {e}")
            return False

    async def update_task_status(
        self,
        page_id: str,
        estado: TaskEstado,
    ) -> bool:
        """Wrapper para actualizar estado de tarea."""
        result = await self.update_task_estado(page_id, estado)
        return result is not None

    async def get_study_projects(self) -> list[dict[str, Any]]:
        """Obtiene proyectos en rotación de estudio."""
        try:
            response = await self.client.databases.query(
                database_id=NotionDatabase.PROJECTS,
                filter={
                    "and": [
                        {"property": "En Rotacion Estudio", "checkbox": {"equals": True}},
                        {"property": "Estado", "select": {"equals": ProjectEstado.ACTIVO.value}},
                    ]
                },
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo proyectos de estudio: {e}")
            return []

    # ==================== NUTRITION ====================
    # Campos: Fecha (Title!), Desayuno (Text), Desayuno Cal (Number),
    #         Desayuno Cat (Select), Comida (Text), Comida Cal (Number),
    #         Comida Cat (Select), Cena (Text), Cena Cal (Number),
    #         Cena Cat (Select), Snacks (Text), Snacks Cal (Number),
    #         Total Cal (Formula), Proteína OK (Checkbox), Vegetales OK (Checkbox),
    #         Evaluación (Select), Notas (Text)

    async def log_nutrition(
        self,
        fecha: str,  # YYYY-MM-DD - Este es el TITLE
        desayuno: str | None = None,
        desayuno_cal: int | None = None,
        desayuno_cat: NutritionCategoria | None = None,
        comida: str | None = None,
        comida_cal: int | None = None,
        comida_cat: NutritionCategoria | None = None,
        cena: str | None = None,
        cena_cal: int | None = None,
        cena_cat: NutritionCategoria | None = None,
        snacks: str | None = None,
        snacks_cal: int | None = None,
        proteina_ok: bool = False,
        vegetales_ok: bool = False,
        evaluacion: NutritionEvaluacion | None = None,
        notas: str | None = None,
    ) -> dict[str, Any] | None:
        """Registra la nutrición del día."""
        try:
            # IMPORTANTE: Fecha es el TITLE en esta base de datos
            properties = {
                "Fecha": {"title": [{"text": {"content": fecha}}]},
                "Proteína OK": {"checkbox": proteina_ok},
                "Vegetales OK": {"checkbox": vegetales_ok},
            }

            if desayuno:
                properties["Desayuno"] = {"rich_text": [{"text": {"content": desayuno}}]}
            if desayuno_cal is not None:
                properties["Desayuno Cal"] = {"number": desayuno_cal}
            if desayuno_cat:
                properties["Desayuno Cat"] = {"select": {"name": desayuno_cat.value}}

            if comida:
                properties["Comida"] = {"rich_text": [{"text": {"content": comida}}]}
            if comida_cal is not None:
                properties["Comida Cal"] = {"number": comida_cal}
            if comida_cat:
                properties["Comida Cat"] = {"select": {"name": comida_cat.value}}

            if cena:
                properties["Cena"] = {"rich_text": [{"text": {"content": cena}}]}
            if cena_cal is not None:
                properties["Cena Cal"] = {"number": cena_cal}
            if cena_cat:
                properties["Cena Cat"] = {"select": {"name": cena_cat.value}}

            if snacks:
                properties["Snacks"] = {"rich_text": [{"text": {"content": snacks}}]}
            if snacks_cal is not None:
                properties["Snacks Cal"] = {"number": snacks_cal}

            if evaluacion:
                properties["Evaluación"] = {"select": {"name": evaluacion.value}}

            if notas:
                properties["Notas"] = {"rich_text": [{"text": {"content": notas}}]}

            response = await self.client.pages.create(
                parent={"database_id": NotionDatabase.NUTRITION},
                properties=properties,
            )
            logger.info(f"Nutrición registrada para {fecha}")
            return response
        except APIResponseError as e:
            logger.error(f"Error registrando nutrición: {e}")
            return None

    async def get_nutrition_history(self, days: int = 7) -> list[dict[str, Any]]:
        """Obtiene historial de nutrición."""
        try:
            response = await self.client.databases.query(
                database_id=NotionDatabase.NUTRITION,
                page_size=days,
                sorts=[{"property": "Fecha", "direction": "descending"}],
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo historial de nutrición: {e}")
            return []

    async def get_or_create_nutrition_for_date(
        self, fecha: str
    ) -> dict[str, Any] | None:
        """Obtiene o crea el registro de nutrición para una fecha."""
        try:
            # Buscar si existe registro para hoy
            response = await self.client.databases.query(
                database_id=NotionDatabase.NUTRITION,
                filter={
                    "property": "Fecha",
                    "title": {"equals": fecha},
                },
                page_size=1,
            )
            results = response.get("results", [])

            if results:
                return results[0]
            else:
                # Crear nuevo registro
                new_record = await self.log_nutrition(fecha=fecha)
                return new_record
        except APIResponseError as e:
            logger.error(f"Error obteniendo/creando nutrición: {e}")
            return None

    async def update_meal(
        self,
        fecha: str,
        meal_type: str,  # desayuno, comida, cena, snack
        description: str,
        calories: int | None = None,
        category: NutritionCategoria | None = None,
    ) -> dict[str, Any] | None:
        """Actualiza una comida específica en el registro del día."""
        try:
            # Obtener o crear el registro del día
            record = await self.get_or_create_nutrition_for_date(fecha)
            if not record:
                return None

            page_id = record.get("id")

            # Mapear tipo de comida a campos de Notion
            meal_fields = {
                "desayuno": ("Desayuno", "Desayuno Cal", "Desayuno Cat"),
                "almuerzo": ("Comida", "Comida Cal", "Comida Cat"),
                "comida": ("Comida", "Comida Cal", "Comida Cat"),
                "cena": ("Cena", "Cena Cal", "Cena Cat"),
                "snack": ("Snacks", "Snacks Cal", None),
            }

            fields = meal_fields.get(meal_type.lower())
            if not fields:
                logger.warning(f"Tipo de comida no reconocido: {meal_type}")
                return None

            text_field, cal_field, cat_field = fields

            # Construir propiedades a actualizar
            properties = {
                text_field: {"rich_text": [{"text": {"content": description}}]},
            }

            if calories is not None:
                properties[cal_field] = {"number": calories}

            if category and cat_field:
                properties[cat_field] = {"select": {"name": category.value}}

            # Actualizar el registro
            response = await self.client.pages.update(
                page_id=page_id,
                properties=properties,
            )
            logger.info(f"Comida {meal_type} actualizada para {fecha}")
            return response

        except APIResponseError as e:
            logger.error(f"Error actualizando comida: {e}")
            return None

    # ==================== WORKOUTS ====================
    # Campos: Fecha (Title!), Tipo (Select), Completado (Checkbox),
    #         Ejercicios (Text - JSON), Sensación (Select), PRs (Text),
    #         Peso Corporal (Number), Notas (Text)

    async def log_workout(
        self,
        fecha: str,  # YYYY-MM-DD - Este es el TITLE
        tipo: WorkoutTipo,
        completado: bool = True,
        ejercicios: list[dict] | None = None,
        sensacion: WorkoutSensacion | None = None,
        prs: str | None = None,
        peso_corporal: float | None = None,
        notas: str | None = None,
    ) -> dict[str, Any] | None:
        """Registra una sesión de entrenamiento."""
        try:
            # IMPORTANTE: Fecha es el TITLE en esta base de datos
            properties = {
                "Fecha": {"title": [{"text": {"content": fecha}}]},
                "Tipo": {"select": {"name": tipo.value}},
                "Completado": {"checkbox": completado},
            }

            if ejercicios:
                # Ejercicios se guarda como JSON string
                ejercicios_json = json.dumps({"exercises": ejercicios}, ensure_ascii=False)
                properties["Ejercicios"] = {
                    "rich_text": [{"text": {"content": ejercicios_json}}]
                }

            if sensacion:
                properties["Sensación"] = {"select": {"name": sensacion.value}}

            if prs:
                properties["PRs"] = {"rich_text": [{"text": {"content": prs}}]}

            if peso_corporal is not None:
                properties["Peso Corporal"] = {"number": peso_corporal}

            if notas:
                properties["Notas"] = {"rich_text": [{"text": {"content": notas}}]}

            response = await self.client.pages.create(
                parent={"database_id": NotionDatabase.WORKOUTS},
                properties=properties,
            )
            logger.info(f"Workout {tipo.value} registrado para {fecha}")
            return response
        except APIResponseError as e:
            logger.error(f"Error registrando workout: {e}")
            return None

    async def get_last_workout_by_type(
        self, tipo: WorkoutTipo
    ) -> dict[str, Any] | None:
        """Obtiene el último workout de un tipo específico."""
        try:
            response = await self.client.databases.query(
                database_id=NotionDatabase.WORKOUTS,
                filter={
                    "and": [
                        {"property": "Tipo", "select": {"equals": tipo.value}},
                        {"property": "Completado", "checkbox": {"equals": True}},
                    ]
                },
                page_size=1,
                sorts=[{"property": "Fecha", "direction": "descending"}],
            )
            results = response.get("results", [])
            return results[0] if results else None
        except APIResponseError as e:
            logger.error(f"Error obteniendo último workout: {e}")
            return None

    async def get_workout_history(self, weeks: int = 4) -> list[dict[str, Any]]:
        """Obtiene historial de workouts."""
        try:
            response = await self.client.databases.query(
                database_id=NotionDatabase.WORKOUTS,
                page_size=weeks * 7,
                sorts=[{"property": "Fecha", "direction": "descending"}],
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo historial de workouts: {e}")
            return []

    # ==================== TRANSACTIONS ====================
    # Campos: Concepto (Title), Monto (Number), Tipo (Select),
    #         Categoría (Select), Fecha (Date), Es Esencial (Checkbox),
    #         Proyecto (Relation), Deuda (Relation), Quincena (Select),
    #         Impulsivo (Checkbox), Notas (Text)

    async def log_transaction(
        self,
        concepto: str,
        monto: float,
        tipo: TransactionTipo,
        categoria: TransactionCategoria,
        fecha: str | None = None,
        es_esencial: bool = False,
        proyecto_id: str | None = None,
        deuda_id: str | None = None,
        quincena: str | None = None,
        impulsivo: bool = False,
        notas: str | None = None,
    ) -> dict[str, Any] | None:
        """Registra una transacción financiera."""
        try:
            if fecha is None:
                fecha = datetime.now().strftime("%Y-%m-%d")

            properties = {
                "Concepto": {"title": [{"text": {"content": concepto}}]},
                "Monto": {"number": monto},
                "Tipo": {"select": {"name": tipo.value}},
                "Categoría": {"select": {"name": categoria.value}},
                "Fecha": {"date": {"start": fecha}},
                "Es Esencial": {"checkbox": es_esencial},
                "Impulsivo": {"checkbox": impulsivo},
            }

            if proyecto_id:
                properties["Proyecto"] = {"relation": [{"id": proyecto_id}]}

            if deuda_id:
                properties["Deuda"] = {"relation": [{"id": deuda_id}]}

            if quincena:
                properties["Quincena"] = {"select": {"name": quincena}}

            if notas:
                properties["Notas"] = {"rich_text": [{"text": {"content": notas}}]}

            response = await self.client.pages.create(
                parent={"database_id": NotionDatabase.TRANSACTIONS},
                properties=properties,
            )
            logger.info(f"Transacción registrada: {concepto} - ${monto}")

            # Si es un pago de deuda, vincular el pago a la deuda (relación inversa Pagos)
            if deuda_id and response and tipo == TransactionTipo.PAGO_DEUDA:
                await self.add_payment_to_debt(deuda_id, response["id"])
                # Invalidar cache de deudas
                await self.invalidate_debts_cache()

            return response
        except APIResponseError as e:
            logger.error(f"Error registrando transacción: {e}")
            return None

    async def add_payment_to_debt(
        self, debt_id: str, transaction_id: str
    ) -> dict[str, Any] | None:
        """
        Agrega una transacción de pago a la relación Pagos de una deuda.

        Args:
            debt_id: ID de la deuda
            transaction_id: ID de la transacción de pago
        """
        try:
            # Obtener pagos actuales de la deuda
            debt = await self.get_page(debt_id)
            if not debt:
                return None

            current_payments = debt.get("properties", {}).get("Pagos", {}).get("relation", [])
            payment_ids = [p["id"] for p in current_payments]

            # Agregar el nuevo pago si no existe
            if transaction_id not in payment_ids:
                payment_ids.append(transaction_id)

            response = await self.client.pages.update(
                page_id=debt_id,
                properties={
                    "Pagos": {"relation": [{"id": pid} for pid in payment_ids]}
                },
            )
            logger.info(f"Pago {transaction_id} vinculado a deuda {debt_id}")
            return response
        except APIResponseError as e:
            logger.error(f"Error vinculando pago a deuda: {e}")
            return None

    async def get_debt_payments(self, debt_id: str) -> list[dict[str, Any]]:
        """
        Obtiene los pagos asociados a una deuda.

        Args:
            debt_id: ID de la deuda
        """
        try:
            debt = await self.get_page(debt_id)
            if not debt:
                return []

            payment_relations = debt.get("properties", {}).get("Pagos", {}).get("relation", [])
            payments = []

            for rel in payment_relations:
                payment = await self.get_page(rel["id"])
                if payment:
                    payments.append(payment)

            return payments
        except APIResponseError as e:
            logger.error(f"Error obteniendo pagos de deuda: {e}")
            return []

    async def get_transactions(
        self,
        tipo: TransactionTipo | None = None,
        categoria: TransactionCategoria | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Obtiene transacciones con filtros opcionales."""
        try:
            filter_conditions = []

            if tipo:
                filter_conditions.append(
                    {"property": "Tipo", "select": {"equals": tipo.value}}
                )

            if categoria:
                filter_conditions.append(
                    {"property": "Categoría", "select": {"equals": categoria.value}}
                )

            filter_config = None
            if filter_conditions:
                if len(filter_conditions) == 1:
                    filter_config = filter_conditions[0]
                else:
                    filter_config = {"and": filter_conditions}

            response = await self.client.databases.query(
                database_id=NotionDatabase.TRANSACTIONS,
                filter=filter_config,
                page_size=limit,
                sorts=[{"property": "Fecha", "direction": "descending"}],
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo transacciones: {e}")
            return []

    async def get_monthly_summary(self) -> dict[str, Any]:
        """Obtiene resumen financiero del mes actual."""
        try:
            # Obtener todas las transacciones del mes
            transactions = await self.get_transactions(limit=100)

            summary = {
                "ingresos": 0.0,
                "gastos_fijos": 0.0,
                "gastos_variables": 0.0,
                "pagos_deuda": 0.0,
                "ahorros": 0.0,
                "total_gastos": 0.0,
                "balance": 0.0,
            }

            for tx in transactions:
                props = tx.get("properties", {})
                monto = props.get("Monto", {}).get("number", 0) or 0
                tipo_prop = props.get("Tipo", {}).get("select", {})
                tipo = tipo_prop.get("name", "") if tipo_prop else ""

                if tipo == TransactionTipo.INGRESO.value:
                    summary["ingresos"] += monto
                elif tipo == TransactionTipo.GASTO_FIJO.value:
                    summary["gastos_fijos"] += abs(monto)
                elif tipo == TransactionTipo.GASTO_VARIABLE.value:
                    summary["gastos_variables"] += abs(monto)
                elif tipo == TransactionTipo.PAGO_DEUDA.value:
                    summary["pagos_deuda"] += abs(monto)
                elif tipo == TransactionTipo.AHORRO.value:
                    summary["ahorros"] += abs(monto)

            summary["total_gastos"] = (
                summary["gastos_fijos"]
                + summary["gastos_variables"]
                + summary["pagos_deuda"]
            )
            summary["balance"] = summary["ingresos"] - summary["total_gastos"]

            return summary
        except Exception as e:
            logger.error(f"Error calculando resumen mensual: {e}")
            return {}

    # ==================== DEBTS ====================
    # Campos: Deuda (Title), Acreedor (Select), Monto Original (Number),
    #         Monto Actual (Number), Tasa Interés (Number),
    #         Interés Mensual (Formula), Pago Mínimo (Number),
    #         Prioridad (Number), Fecha Inicio (Date), Fecha Límite (Date),
    #         Pagos (Relation), Progreso (Formula), Estado (Select), Notas (Text)

    async def get_debts(
        self, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Obtiene la lista de deudas."""
        try:
            filter_config = None
            if active_only:
                filter_config = {
                    "property": "Estado",
                    "select": {"equals": DebtEstado.ACTIVA.value},
                }

            response = await self.client.databases.query(
                database_id=NotionDatabase.DEBTS,
                filter=filter_config,
                sorts=[{"property": "Prioridad", "direction": "ascending"}],
            )
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error obteniendo deudas: {e}")
            return []

    async def update_debt_amount(
        self, page_id: str, monto_actual: float, auto_liquidate: bool = True
    ) -> dict[str, Any] | None:
        """
        Actualiza el monto actual de una deuda.

        Args:
            page_id: ID de la deuda
            monto_actual: Nuevo monto actual
            auto_liquidate: Si True, cambia estado a Liquidada cuando monto <= 0
        """
        try:
            properties = {"Monto Actual": {"number": max(0, monto_actual)}}

            # Auto-liquidar si el monto llega a 0 o menos
            if auto_liquidate and monto_actual <= 0:
                properties["Estado"] = {"select": {"name": DebtEstado.LIQUIDADA.value}}
                logger.info(f"Deuda {page_id} liquidada automáticamente")

            response = await self.client.pages.update(
                page_id=page_id,
                properties=properties,
            )
            logger.info(f"Deuda {page_id} actualizada a ${monto_actual}")

            # Invalidar cache
            await self.invalidate_debts_cache()

            return response
        except APIResponseError as e:
            logger.error(f"Error actualizando deuda: {e}")
            return None

    async def apply_payment_to_debt(
        self,
        debt_id: str,
        payment_amount: float,
        concepto: str | None = None,
    ) -> dict[str, Any]:
        """
        Aplica un pago a una deuda: crea transacción, vincula, y actualiza monto.

        Esta es una función de conveniencia que:
        1. Crea la transacción de pago
        2. Vincula el pago a la deuda
        3. Actualiza el monto actual de la deuda

        Args:
            debt_id: ID de la deuda
            payment_amount: Monto del pago
            concepto: Descripción del pago (opcional)

        Returns:
            Dict con transaction, debt_updated, y nuevo monto
        """
        try:
            # Obtener deuda actual
            debt = await self.get_page(debt_id)
            if not debt:
                return {"error": "Deuda no encontrada"}

            props = debt.get("properties", {})

            # Obtener nombre de la deuda para el concepto
            debt_name = ""
            title_prop = props.get("Deuda", {}).get("title", [])
            if title_prop:
                debt_name = title_prop[0].get("text", {}).get("content", "")

            monto_actual = props.get("Monto Actual", {}).get("number", 0) or 0

            # Crear transacción de pago
            tx_concepto = concepto or f"Pago a {debt_name}"
            transaction = await self.log_transaction(
                concepto=tx_concepto,
                monto=payment_amount,
                tipo=TransactionTipo.PAGO_DEUDA,
                categoria=TransactionCategoria.DEUDA,
                deuda_id=debt_id,
            )

            # Calcular nuevo monto
            nuevo_monto = monto_actual - payment_amount

            # Actualizar deuda
            debt_updated = await self.update_debt_amount(debt_id, nuevo_monto)

            return {
                "transaction": transaction,
                "debt_updated": debt_updated,
                "monto_anterior": monto_actual,
                "monto_nuevo": max(0, nuevo_monto),
                "liquidada": nuevo_monto <= 0,
            }
        except Exception as e:
            logger.error(f"Error aplicando pago a deuda: {e}")
            return {"error": str(e)}

    async def get_debt_summary(self, use_cache: bool = True) -> dict[str, Any]:
        """Obtiene resumen de deudas."""
        cache = get_cache()
        cache_key = NotionCacheKeys.DEBT_SUMMARY

        if use_cache:
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        try:
            debts = await self.get_debts(active_only=True)

            summary = {
                "total_deuda": 0.0,
                "total_pago_minimo": 0.0,
                "total_interes_mensual": 0.0,
                "deudas": [],
            }

            for debt in debts:
                props = debt.get("properties", {})
                nombre = ""
                title_prop = props.get("Deuda", {}).get("title", [])
                if title_prop:
                    nombre = title_prop[0].get("text", {}).get("content", "")

                monto_actual = props.get("Monto Actual", {}).get("number", 0) or 0
                pago_minimo = props.get("Pago Mínimo", {}).get("number", 0) or 0
                tasa = props.get("Tasa Interés", {}).get("number", 0) or 0
                interes_mensual = monto_actual * (tasa / 100) / 12

                summary["total_deuda"] += monto_actual
                summary["total_pago_minimo"] += pago_minimo
                summary["total_interes_mensual"] += interes_mensual
                summary["deudas"].append({
                    "nombre": nombre,
                    "monto": monto_actual,
                    "pago_minimo": pago_minimo,
                    "tasa": tasa,
                    "interes_mensual": interes_mensual,
                })

            # Cache por 10 minutos (deudas no cambian frecuentemente)
            await cache.set(cache_key, summary, ttl=600)

            return summary
        except Exception as e:
            log_error(e, "get_debt_summary", ErrorCategory.API_NOTION)
            return {}

    # ==================== KNOWLEDGE ====================
    # Campos: Título (Title), Contenido (Text), Tipo (Select),
    #         Topic (Multi-select), Fuente (Select), Valor (Select),
    #         Proyecto (Relation), Task (Relation), Evergreen (Checkbox),
    #         Fecha (Date)

    async def create_knowledge(
        self,
        titulo: str,
        contenido: str,
        tipo: KnowledgeTipo = KnowledgeTipo.NOTA,
        topics: list[str] | None = None,
        fuente: str = "Personal",
        proyecto_id: str | None = None,
        task_id: str | None = None,
        evergreen: bool = False,
    ) -> dict[str, Any] | None:
        """
        Crea una entrada en Knowledge.

        Args:
            titulo: Título del conocimiento
            contenido: Contenido/descripción
            tipo: Tipo de conocimiento (Nota, Idea, Artículo, etc.)
            topics: Lista de topics/tags
            fuente: Fuente del conocimiento
            proyecto_id: ID del proyecto relacionado
            task_id: ID de la tarea relacionada (nuevo)
            evergreen: Si es contenido evergreen
        """
        try:
            properties = {
                "Título": {"title": [{"text": {"content": titulo}}]},
                "Contenido": {"rich_text": [{"text": {"content": contenido}}]},
                "Tipo": {"select": {"name": tipo.value}},
                "Fuente": {"select": {"name": fuente}},
                "Evergreen": {"checkbox": evergreen},
                "Fecha": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
            }

            if topics:
                properties["Topic"] = {
                    "multi_select": [{"name": t} for t in topics]
                }

            if proyecto_id:
                properties["Proyecto"] = {"relation": [{"id": proyecto_id}]}

            # Relación Task → Tasks (nueva)
            if task_id:
                properties["Task"] = {"relation": [{"id": task_id}]}

            response = await self.client.pages.create(
                parent={"database_id": NotionDatabase.KNOWLEDGE},
                properties=properties,
            )
            logger.info(f"Knowledge creado: {titulo}")
            return response
        except APIResponseError as e:
            logger.error(f"Error creando knowledge: {e}")
            return None

    # ==================== UTILS ====================

    async def get_page(self, page_id: str) -> dict[str, Any] | None:
        """Obtiene una página por ID."""
        try:
            return await self.client.pages.retrieve(page_id=page_id)
        except APIResponseError as e:
            logger.error(f"Error obteniendo página {page_id}: {e}")
            return None

    async def search(
        self, query: str, filter_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Busca en Notion."""
        try:
            params = {"query": query}
            if filter_type:
                params["filter"] = {"property": "object", "value": filter_type}

            response = await self.client.search(**params)
            return response.get("results", [])
        except APIResponseError as e:
            logger.error(f"Error buscando '{query}': {e}")
            return []

    async def test_connection(self) -> bool:
        """Verifica la conexión con Notion."""
        try:
            await self.client.users.me()
            logger.info("Conexión con Notion exitosa")
            return True
        except APIResponseError as e:
            logger.error(f"Error de conexión con Notion: {e}")
            return False

    async def invalidate_cache(self, pattern: str = "notion:") -> int:
        """
        Invalida entradas del cache que coincidan con el patrón.

        Args:
            pattern: Prefijo de las claves a invalidar

        Returns:
            Número de entradas eliminadas
        """
        cache = get_cache()
        count = await cache.clear_pattern(pattern)
        logger.info(f"Cache invalidado: {count} entradas con patrón '{pattern}'")
        return count

    async def invalidate_tasks_cache(self) -> None:
        """Invalida el cache de tareas."""
        cache = get_cache()
        await cache.delete(NotionCacheKeys.TASKS_TODAY)
        await cache.delete(NotionCacheKeys.TASKS_PENDING)

    async def invalidate_projects_cache(self) -> None:
        """Invalida el cache de proyectos."""
        await self.invalidate_cache("notion:projects:")

    async def invalidate_debts_cache(self) -> None:
        """Invalida el cache de deudas."""
        cache = get_cache()
        await cache.delete(NotionCacheKeys.DEBTS_ACTIVE)
        await cache.delete(NotionCacheKeys.DEBT_SUMMARY)


# Singleton
_notion_service: NotionService | None = None


def get_notion_service() -> NotionService:
    """Obtiene la instancia del servicio de Notion."""
    global _notion_service
    if _notion_service is None:
        _notion_service = NotionService()
    return _notion_service
