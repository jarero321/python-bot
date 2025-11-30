"""ConversationalOrchestrator - Orquestador con contexto conversacional."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import dspy

from app.agents.base import setup_dspy
from app.agents.conversation_context import (
    ConversationContext,
    ConversationState,
    EntityType,
    ActiveEntity,
    get_conversation_store,
)
from app.agents.orchestrator import AgentOrchestrator, get_orchestrator
from app.agents.intent_router import IntentRouterAgent, UserIntent, IntentResult, get_intent_router
from app.services.notion import (
    get_notion_service,
    TaskEstado,
    TaskPrioridad,
)

logger = logging.getLogger(__name__)


class ContextualIntentSignature(dspy.Signature):
    """Clasifica intención considerando el contexto conversacional."""

    message: str = dspy.InputField(desc="Mensaje del usuario")
    conversation_history: str = dspy.InputField(desc="Últimos mensajes de la conversación")
    active_context: str = dspy.InputField(desc="Contexto activo (entidad, subtareas, etc.)")
    pending_action: str = dspy.InputField(desc="Acción pendiente si existe")

    is_contextual: bool = dspy.OutputField(
        desc="True si el mensaje hace referencia al contexto anterior"
    )
    contextual_action: str = dspy.OutputField(
        desc="""Acción contextual si aplica:
        - modify_subtasks: quiere modificar subtareas (quitar, añadir, cambiar)
        - confirm: confirma la acción pendiente (sí, ok, perfecto, dale)
        - reject: rechaza la acción (no, mejor no, cancela)
        - add_blocker: quiere añadir un bloqueador
        - remove_blocker: quiere quitar un bloqueador
        - change_priority: quiere cambiar prioridad
        - reschedule: quiere cambiar fecha/tiempo
        - request_extension: necesita más tiempo
        - edit_entity: quiere editar la entidad activa
        - delete_entity: quiere eliminar la entidad
        - none: no es una acción contextual
        """
    )
    referenced_items: str = dspy.OutputField(
        desc="Items referenciados (ej: 'la 3', 'esa tarea', 'las primeras dos') separados por coma"
    )
    modification_details: str = dspy.OutputField(
        desc="Detalles de la modificación si aplica (ej: nuevas subtareas a añadir)"
    )


@dataclass
class ConversationalResponse:
    """Respuesta del orquestador conversacional."""
    message: str
    intent: UserIntent
    is_contextual: bool
    contextual_action: str | None
    requires_callback: bool = False
    callback_data: dict | None = None
    keyboard_options: list[list[dict]] | None = None  # Para botones inline
    entity_updated: bool = False
    context_cleared: bool = False


class ConversationalOrchestrator:
    """
    Orquestador que mantiene contexto conversacional y coordina todos los agentes.

    Responsabilidades:
    1. Mantener contexto entre mensajes (última tarea, subtareas sugeridas, etc.)
    2. Entender referencias contextuales ("la 3", "esa tarea", "quita dos")
    3. Permitir modificaciones conversacionales de entidades
    4. Coordinar con AgentOrchestrator para el trabajo pesado
    5. Gestionar flujo de confirmaciones
    """

    def __init__(self):
        setup_dspy()
        self.store = get_conversation_store()
        self.base_orchestrator = get_orchestrator()
        self.intent_router = get_intent_router()
        self.contextual_classifier = dspy.ChainOfThought(ContextualIntentSignature)

        # Patrones para detectar referencias numéricas
        self.number_patterns = [
            (r"(?:la|el|las|los)\s+(\d+)", "single"),  # "la 3", "el 2"
            (r"(?:quita|elimina|borra)\s+(?:la|el)?\s*(\d+)", "remove"),  # "quita la 3"
            (r"(?:las|los)\s+(?:primeras?|últimas?)\s+(\d+)", "range"),  # "las primeras 2"
            (r"(\d+)\s*(?:y|,)\s*(\d+)", "multiple"),  # "2 y 3", "1, 4"
        ]

        # Palabras de confirmación/rechazo
        self.confirm_words = ["sí", "si", "ok", "okay", "dale", "perfecto", "listo", "adelante", "correcto", "está bien"]
        self.reject_words = ["no", "mejor no", "cancela", "cancelar", "olvídalo", "dejalo", "nada"]

    async def process_message(
        self,
        user_id: int,
        message: str,
    ) -> ConversationalResponse:
        """
        Procesa un mensaje considerando el contexto conversacional.

        Args:
            user_id: ID del usuario de Telegram
            message: Mensaje del usuario

        Returns:
            ConversationalResponse con la respuesta y metadata
        """
        # 1. Obtener contexto del usuario
        ctx = self.store.get(user_id)

        # 2. Verificar si es respuesta rápida (sí/no)
        quick_response = self._check_quick_response(message, ctx)
        if quick_response:
            self.store.save(ctx)
            return quick_response

        # 3. Verificar si es una acción contextual
        if ctx.active_entity or ctx.pending_action:
            contextual_result = await self._process_contextual(message, ctx)
            if contextual_result:
                self.store.save(ctx)
                return contextual_result

        # 4. Procesar como mensaje nuevo con IntentRouter
        intent_result = await self.intent_router.execute(
            message=message,
            conversation_context=ctx.get_history_summary(),
        )

        # 5. Agregar mensaje al historial
        ctx.add_message(
            role="user",
            content=message,
            intent=intent_result.intent.value,
            entities=intent_result.entities,
        )

        # 6. Procesar según intención usando el orquestador base
        response = await self._route_intent(intent_result, message, ctx)

        # 7. Agregar respuesta al historial
        ctx.add_message(role="assistant", content=response.message[:200])

        # 8. Guardar contexto
        self.store.save(ctx)

        return response

    def _check_quick_response(
        self,
        message: str,
        ctx: ConversationContext,
    ) -> ConversationalResponse | None:
        """Verifica si es una respuesta rápida de confirmación/rechazo."""
        message_lower = message.lower().strip()

        # Solo aplica si hay acción pendiente
        if not ctx.pending_action or ctx.pending_action.is_expired():
            return None

        # Confirmación
        if any(word in message_lower for word in self.confirm_words):
            return self._handle_confirmation(ctx)

        # Rechazo
        if any(word in message_lower for word in self.reject_words):
            return self._handle_rejection(ctx)

        return None

    def _handle_confirmation(self, ctx: ConversationContext) -> ConversationalResponse:
        """Maneja confirmación de acción pendiente."""
        action = ctx.pending_action

        if action.action_type == "create_subtasks":
            # Crear subtareas confirmadas
            subtasks = action.data.get("subtasks", [])
            ctx.active_entity.subtasks = subtasks
            ctx.clear_pending_action()
            ctx.state = ConversationState.IDLE

            return ConversationalResponse(
                message=f"Subtareas añadidas:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(subtasks)),
                intent=UserIntent.TASK_CREATE,
                is_contextual=True,
                contextual_action="confirm",
                entity_updated=True,
            )

        elif action.action_type == "delete_entity":
            entity_name = ctx.active_entity.entity_name if ctx.active_entity else "elemento"
            ctx.clear_active_entity()
            ctx.clear_pending_action()

            return ConversationalResponse(
                message=f"{entity_name} eliminado.",
                intent=UserIntent.TASK_DELETE,
                is_contextual=True,
                contextual_action="confirm",
                context_cleared=True,
            )

        # Default
        ctx.clear_pending_action()
        return ConversationalResponse(
            message="Acción completada.",
            intent=UserIntent.UNKNOWN,
            is_contextual=True,
            contextual_action="confirm",
        )

    def _handle_rejection(self, ctx: ConversationContext) -> ConversationalResponse:
        """Maneja rechazo de acción pendiente."""
        ctx.clear_pending_action()
        ctx.state = ConversationState.IDLE

        return ConversationalResponse(
            message="Entendido, cancelado.",
            intent=UserIntent.UNKNOWN,
            is_contextual=True,
            contextual_action="reject",
        )

    async def _process_contextual(
        self,
        message: str,
        ctx: ConversationContext,
    ) -> ConversationalResponse | None:
        """Procesa mensaje en contexto de entidad activa."""
        try:
            # Usar LLM para entender la acción contextual
            result = self.contextual_classifier(
                message=message,
                conversation_history=ctx.get_history_summary(),
                active_context=ctx.get_context_summary(),
                pending_action=ctx.pending_action.action_type if ctx.pending_action else "ninguna",
            )

            if not result.is_contextual:
                return None

            action = str(result.contextual_action).lower().strip()

            # Modificar subtareas
            if action == "modify_subtasks":
                return await self._handle_subtask_modification(
                    message, ctx, result.referenced_items, result.modification_details
                )

            # Añadir blocker
            elif action == "add_blocker":
                return await self._handle_add_blocker(message, ctx, result.modification_details)

            # Cambiar prioridad
            elif action == "change_priority":
                return await self._handle_priority_change(message, ctx)

            # Reprogramar
            elif action == "reschedule":
                return await self._handle_reschedule(message, ctx, result.modification_details)

            # Confirmar
            elif action == "confirm":
                return self._handle_confirmation(ctx)

            # Rechazar
            elif action == "reject":
                return self._handle_rejection(ctx)

            # Editar entidad
            elif action == "edit_entity":
                return await self._handle_edit_entity(message, ctx)

            # Eliminar entidad
            elif action == "delete_entity":
                return await self._handle_delete_entity(ctx)

            return None

        except Exception as e:
            logger.error(f"Error procesando contextual: {e}")
            return None

    async def _handle_subtask_modification(
        self,
        message: str,
        ctx: ConversationContext,
        referenced_items: str,
        modification_details: str,
    ) -> ConversationalResponse:
        """Maneja modificación de subtareas."""
        if not ctx.active_entity:
            return ConversationalResponse(
                message="No hay tarea activa para modificar subtareas.",
                intent=UserIntent.UNKNOWN,
                is_contextual=True,
                contextual_action="error",
            )

        # Obtener subtareas actuales
        current_subtasks = ctx.active_entity.suggested_subtasks or ctx.active_entity.subtasks or []

        # Detectar qué subtareas quitar
        to_remove = self._parse_item_references(referenced_items, len(current_subtasks))

        # Detectar subtareas a añadir
        to_add = self._extract_new_items(modification_details)

        # Aplicar cambios
        new_subtasks = [s for i, s in enumerate(current_subtasks, 1) if i not in to_remove]
        new_subtasks.extend(to_add)

        # Actualizar contexto
        ctx.active_entity.suggested_subtasks = new_subtasks

        # Construir mensaje
        changes = []
        if to_remove:
            removed_names = [current_subtasks[i-1] for i in to_remove if i <= len(current_subtasks)]
            changes.append(f"Quitadas: {', '.join(removed_names)}")
        if to_add:
            changes.append(f"Añadidas: {', '.join(to_add)}")

        message_parts = ["Subtareas actualizadas:"]
        for i, subtask in enumerate(new_subtasks, 1):
            message_parts.append(f"  {i}. {subtask}")

        if changes:
            message_parts.append(f"\nCambios: {' | '.join(changes)}")

        return ConversationalResponse(
            message="\n".join(message_parts),
            intent=UserIntent.TASK_UPDATE,
            is_contextual=True,
            contextual_action="modify_subtasks",
            entity_updated=True,
        )

    async def _handle_add_blocker(
        self,
        message: str,
        ctx: ConversationContext,
        details: str,
    ) -> ConversationalResponse:
        """Maneja añadir un blocker a la tarea activa."""
        if not ctx.active_entity or ctx.active_entity.entity_type != EntityType.TASK:
            return ConversationalResponse(
                message="No hay tarea activa para añadir blocker.",
                intent=UserIntent.UNKNOWN,
                is_contextual=True,
                contextual_action="error",
            )

        # Extraer razón del blocker
        blocker_reason = details or message

        # Limpiar texto
        blocker_reason = re.sub(r"(?i)(añade|agrega|pon)\s+(un\s+)?blocker:?\s*", "", blocker_reason).strip()

        if not blocker_reason:
            return ConversationalResponse(
                message="¿Cuál es el blocker? (ej: 'esperando respuesta del cliente')",
                intent=UserIntent.TASK_UPDATE,
                is_contextual=True,
                contextual_action="awaiting_input",
            )

        # Añadir blocker
        ctx.active_entity.blockers.append(blocker_reason)

        # Actualizar en Notion si hay ID
        if ctx.active_entity.entity_id:
            try:
                notion = get_notion_service()
                await notion.set_task_blocker(ctx.active_entity.entity_id, blocker_reason)
            except Exception as e:
                logger.error(f"Error guardando blocker en Notion: {e}")

        return ConversationalResponse(
            message=f"Blocker añadido a '{ctx.active_entity.entity_name}':\n  {blocker_reason}",
            intent=UserIntent.TASK_UPDATE,
            is_contextual=True,
            contextual_action="add_blocker",
            entity_updated=True,
        )

    async def _handle_priority_change(
        self,
        message: str,
        ctx: ConversationContext,
    ) -> ConversationalResponse:
        """Maneja cambio de prioridad."""
        if not ctx.active_entity:
            return ConversationalResponse(
                message="No hay entidad activa para cambiar prioridad.",
                intent=UserIntent.UNKNOWN,
                is_contextual=True,
                contextual_action="error",
            )

        # Detectar nueva prioridad
        message_lower = message.lower()
        new_priority = None

        if any(w in message_lower for w in ["urgente", "crítico", "asap"]):
            new_priority = TaskPrioridad.URGENTE
        elif any(w in message_lower for w in ["alta", "importante"]):
            new_priority = TaskPrioridad.ALTA
        elif any(w in message_lower for w in ["normal", "media"]):
            new_priority = TaskPrioridad.NORMAL
        elif any(w in message_lower for w in ["baja", "después"]):
            new_priority = TaskPrioridad.BAJA

        if not new_priority:
            return ConversationalResponse(
                message="¿Qué prioridad? (urgente, alta, normal, baja)",
                intent=UserIntent.TASK_UPDATE,
                is_contextual=True,
                contextual_action="awaiting_input",
                keyboard_options=[[
                    {"text": "🔥 Urgente", "callback": "priority_urgente"},
                    {"text": "⚡ Alta", "callback": "priority_alta"},
                ], [
                    {"text": "🔄 Normal", "callback": "priority_normal"},
                    {"text": "🧊 Baja", "callback": "priority_baja"},
                ]],
            )

        # Actualizar en Notion
        if ctx.active_entity.entity_id:
            try:
                notion = get_notion_service()
                await notion.update_task_priority(ctx.active_entity.entity_id, new_priority)
            except Exception as e:
                logger.error(f"Error actualizando prioridad: {e}")

        return ConversationalResponse(
            message=f"Prioridad de '{ctx.active_entity.entity_name}' cambiada a: {new_priority.value}",
            intent=UserIntent.TASK_UPDATE,
            is_contextual=True,
            contextual_action="change_priority",
            entity_updated=True,
        )

    async def _handle_reschedule(
        self,
        message: str,
        ctx: ConversationContext,
        details: str,
    ) -> ConversationalResponse:
        """Maneja reprogramación de tarea."""
        if not ctx.active_entity:
            return ConversationalResponse(
                message="No hay tarea activa para reprogramar.",
                intent=UserIntent.UNKNOWN,
                is_contextual=True,
                contextual_action="error",
            )

        # Detectar nueva fecha
        from datetime import timedelta
        now = datetime.now()
        new_date = None

        message_lower = message.lower()
        if "mañana" in message_lower:
            new_date = now + timedelta(days=1)
        elif "pasado" in message_lower or "pasado mañana" in message_lower:
            new_date = now + timedelta(days=2)
        elif "próxima semana" in message_lower or "lunes" in message_lower:
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            new_date = now + timedelta(days=days_until_monday)
        elif "viernes" in message_lower:
            days_until_friday = (4 - now.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            new_date = now + timedelta(days=days_until_friday)

        if not new_date:
            return ConversationalResponse(
                message="¿Para cuándo? (mañana, pasado mañana, próxima semana, viernes)",
                intent=UserIntent.TASK_UPDATE,
                is_contextual=True,
                contextual_action="awaiting_input",
            )

        date_str = new_date.strftime("%Y-%m-%d")
        date_display = new_date.strftime("%d/%m")

        # Actualizar en Notion
        if ctx.active_entity.entity_id:
            try:
                notion = get_notion_service()
                await notion.update_task_dates(ctx.active_entity.entity_id, fecha_do=date_str)
            except Exception as e:
                logger.error(f"Error reprogramando: {e}")

        return ConversationalResponse(
            message=f"'{ctx.active_entity.entity_name}' reprogramada para: {date_display}",
            intent=UserIntent.TASK_UPDATE,
            is_contextual=True,
            contextual_action="reschedule",
            entity_updated=True,
        )

    async def _handle_edit_entity(
        self,
        message: str,
        ctx: ConversationContext,
    ) -> ConversationalResponse:
        """Maneja edición de entidad activa."""
        if not ctx.active_entity:
            return ConversationalResponse(
                message="No hay entidad activa para editar.",
                intent=UserIntent.UNKNOWN,
                is_contextual=True,
                contextual_action="error",
            )

        # Ofrecer opciones de edición
        ctx.state = ConversationState.EDITING_ENTITY

        return ConversationalResponse(
            message=f"Editando: {ctx.active_entity.entity_name}\n¿Qué quieres modificar?",
            intent=UserIntent.TASK_UPDATE,
            is_contextual=True,
            contextual_action="edit_entity",
            keyboard_options=[[
                {"text": "📝 Nombre", "callback": "edit_name"},
                {"text": "🎯 Estado", "callback": "edit_status"},
            ], [
                {"text": "🔥 Prioridad", "callback": "edit_priority"},
                {"text": "📅 Fecha", "callback": "edit_date"},
            ], [
                {"text": "❌ Cancelar", "callback": "edit_cancel"},
            ]],
        )

    async def _handle_delete_entity(
        self,
        ctx: ConversationContext,
    ) -> ConversationalResponse:
        """Maneja eliminación de entidad activa."""
        if not ctx.active_entity:
            return ConversationalResponse(
                message="No hay entidad activa para eliminar.",
                intent=UserIntent.UNKNOWN,
                is_contextual=True,
                contextual_action="error",
            )

        # Pedir confirmación
        ctx.set_pending_action(
            action_type="delete_entity",
            target_entity=ctx.active_entity.entity_type,
            target_id=ctx.active_entity.entity_id,
        )
        ctx.state = ConversationState.AWAITING_CONFIRMATION

        return ConversationalResponse(
            message=f"¿Eliminar '{ctx.active_entity.entity_name}'?",
            intent=UserIntent.TASK_DELETE,
            is_contextual=True,
            contextual_action="awaiting_confirmation",
            keyboard_options=[[
                {"text": "✅ Sí, eliminar", "callback": "confirm_delete"},
                {"text": "❌ No, cancelar", "callback": "cancel_delete"},
            ]],
        )

    def _parse_item_references(self, references: str, max_items: int) -> set[int]:
        """Parsea referencias a items (la 3, las primeras 2, etc.)."""
        items = set()

        if not references:
            return items

        # Buscar números directos
        numbers = re.findall(r"\d+", references)
        for num in numbers:
            n = int(num)
            if 1 <= n <= max_items:
                items.add(n)

        # Buscar rangos (las primeras X)
        if "primer" in references.lower():
            count = int(numbers[0]) if numbers else 1
            items.update(range(1, min(count + 1, max_items + 1)))

        # Buscar últimas X
        if "últim" in references.lower():
            count = int(numbers[0]) if numbers else 1
            items.update(range(max(1, max_items - count + 1), max_items + 1))

        return items

    def _extract_new_items(self, details: str) -> list[str]:
        """Extrae nuevos items de los detalles de modificación."""
        if not details:
            return []

        # Limpiar prefijos comunes
        details = re.sub(r"(?i)(añade|agrega|incluye|pon):?\s*", "", details)

        # Separar por comas, "y", o saltos de línea
        items = re.split(r"[,\n]|\s+y\s+", details)

        # Limpiar cada item
        return [item.strip() for item in items if item.strip() and len(item.strip()) > 2]

    async def _route_intent(
        self,
        intent_result: IntentResult,
        message: str,
        ctx: ConversationContext,
    ) -> ConversationalResponse:
        """Enruta según la intención usando el orquestador base."""
        intent = intent_result.intent
        entities = intent_result.entities

        # Usar el orquestador base para enriquecer
        try:
            enriched = await self.base_orchestrator.process_message(
                message=message,
                user_id=ctx.user_id,
                conversation_context=ctx.get_history_summary(),
            )
        except Exception as e:
            logger.error(f"Error en orquestador base: {e}")
            enriched = {"enrichment": {}}

        enrichment = enriched.get("enrichment", {})

        # TASK_CREATE - Usar planificación completa
        if intent == UserIntent.TASK_CREATE:
            return await self._handle_task_create(message, entities, enrichment, ctx)

        # PROJECT_CREATE
        elif intent == UserIntent.PROJECT_CREATE:
            return await self._handle_project_create(message, entities, enrichment, ctx)

        # Otros intents - respuestas básicas
        elif intent == UserIntent.GREETING:
            return ConversationalResponse(
                message=intent_result.suggested_response or "¡Hola! ¿En qué te ayudo?",
                intent=intent,
                is_contextual=False,
                contextual_action=None,
            )

        elif intent == UserIntent.HELP:
            return ConversationalResponse(
                message=self._get_help_message(),
                intent=intent,
                is_contextual=False,
                contextual_action=None,
            )

        # Default
        return ConversationalResponse(
            message=f"Entendido: {intent.value}. Procesando...",
            intent=intent,
            is_contextual=False,
            contextual_action=None,
        )

    async def _handle_task_create(
        self,
        message: str,
        entities: dict,
        enrichment: dict,
        ctx: ConversationContext,
    ) -> ConversationalResponse:
        """Maneja creación de tarea con contexto."""
        task_name = entities.get("task", message)
        complexity = enrichment.get("complexity", {})
        subtasks = complexity.get("subtasks", [])
        blockers = complexity.get("blockers", [])

        # Crear tarea en Notion
        notion = get_notion_service()

        try:
            result = await notion.create_task(
                tarea=task_name[:200],
                estado=TaskEstado.BACKLOG,
            )
            task_id = result.get("id") if result else None
        except Exception as e:
            logger.error(f"Error creando tarea: {e}")
            task_id = None

        # Establecer como entidad activa
        ctx.set_active_entity(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            entity_name=task_name[:100],
            entity_data=enrichment,
            suggested_subtasks=subtasks,
        )

        # Construir respuesta
        msg_parts = [f"Tarea creada: <b>{task_name}</b>"]

        if subtasks:
            msg_parts.append("\nSubtareas sugeridas:")
            for i, sub in enumerate(subtasks[:5], 1):
                msg_parts.append(f"  {i}. {sub}")
            msg_parts.append("\n<i>Puedes decir 'quita la 3' o 'añade otra subtarea'</i>")

            # Poner acción pendiente para confirmar subtareas
            ctx.set_pending_action(
                action_type="create_subtasks",
                target_entity=EntityType.TASK,
                target_id=task_id,
                data={"subtasks": subtasks},
            )
            ctx.state = ConversationState.REVIEWING_SUBTASKS

        if blockers:
            msg_parts.append("\nPosibles blockers:")
            for blocker in blockers[:3]:
                msg_parts.append(f"  ⚠️ {blocker}")

        return ConversationalResponse(
            message="\n".join(msg_parts),
            intent=UserIntent.TASK_CREATE,
            is_contextual=False,
            contextual_action=None,
            keyboard_options=[[
                {"text": "✅ Crear subtareas", "callback": "confirm_subtasks"},
                {"text": "✏️ Modificar", "callback": "modify_subtasks"},
            ], [
                {"text": "❌ Sin subtareas", "callback": "skip_subtasks"},
            ]] if subtasks else None,
        )

    async def _handle_project_create(
        self,
        message: str,
        entities: dict,
        enrichment: dict,
        ctx: ConversationContext,
    ) -> ConversationalResponse:
        """Maneja creación de proyecto."""
        project_name = entities.get("project_name", message)

        # Establecer como entidad activa
        ctx.set_active_entity(
            entity_type=EntityType.PROJECT,
            entity_name=project_name,
            entity_data=enrichment,
        )

        return ConversationalResponse(
            message=f"Proyecto: <b>{project_name}</b>\n¿Qué tipo de proyecto es?",
            intent=UserIntent.PROJECT_CREATE,
            is_contextual=False,
            contextual_action=None,
            keyboard_options=[[
                {"text": "💼 Trabajo", "callback": "project_type_trabajo"},
                {"text": "💻 Freelance", "callback": "project_type_freelance"},
            ], [
                {"text": "📚 Estudio", "callback": "project_type_estudio"},
                {"text": "🏠 Personal", "callback": "project_type_personal"},
            ]],
        )

    def _get_help_message(self) -> str:
        """Genera mensaje de ayuda."""
        return """<b>Carlos Command</b>

<b>Comandos:</b>
/today - Tareas de hoy
/add [tarea] - Nueva tarea
/projects - Ver proyectos
/gym - Registrar workout
/food - Registrar comida
/deepwork - Iniciar focus

<b>Conversación natural:</b>
• "Crear tarea: revisar API"
• "Quita la subtarea 3"
• "Añade blocker: esperando cliente"
• "Mueve esto a mañana"
• "Es más urgente"

<b>Finanzas:</b>
• "Me quiero comprar X por $Y"
• "¿Cuánto debo?"
"""


# Singleton
_conversational_orchestrator: ConversationalOrchestrator | None = None


def get_conversational_orchestrator() -> ConversationalOrchestrator:
    """Obtiene la instancia del orquestador conversacional."""
    global _conversational_orchestrator
    if _conversational_orchestrator is None:
        _conversational_orchestrator = ConversationalOrchestrator()
    return _conversational_orchestrator
