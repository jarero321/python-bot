"""
UnifiedOrchestrator - Orquestador unificado usando EnricherRegistry.

Arquitectura limpia sin if/else:
    Message → IntentRouter → EnricherRegistry → Handler

Este orquestador:
1. Mantiene contexto conversacional entre mensajes
2. Clasifica intención con el IntentRouter
3. Enriquece con EnricherRegistry (sin if/else)
4. Retorna resultado enriquecido para el handler
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.agents.base import setup_dspy
from app.agents.intent_router import (
    IntentRouterAgent,
    UserIntent,
    IntentResult,
    get_intent_router,
)
from app.agents.conversation_context import (
    ConversationContext,
    ConversationState,
    EntityType,
    get_conversation_store,
)
from app.agents.enrichers import (
    EnricherRegistry,
    EnrichmentResult,
    get_enricher_registry,
    register_all_enrichers,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResponse:
    """Respuesta del orquestador unificado."""

    message: str
    intent: UserIntent
    enrichment: EnrichmentResult | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    # Control de flujo
    is_contextual: bool = False
    already_handled: bool = False

    # UI
    keyboard_options: list[list[dict]] | None = None

    # Metadata
    processing_time_ms: int = 0
    agents_used: list[str] = field(default_factory=list)

    def get_enriched_entities(self) -> dict[str, Any]:
        """Retorna entities con el enriquecimiento incluido."""
        result = dict(self.entities)
        if self.enrichment:
            result.update(self.enrichment.to_entities_dict())
        return result


class UnifiedOrchestrator:
    """
    Orquestador unificado que coordina todos los agentes del sistema.

    Usa el patrón EnricherRegistry para eliminar if/else:
    - Cada dominio tiene su propio Enricher
    - El registry mapea intents a enrichers automáticamente
    - Agregar un nuevo dominio = crear un nuevo Enricher y registrarlo
    """

    def __init__(self):
        setup_dspy()
        self.logger = logging.getLogger("unified_orchestrator")

        # Contexto conversacional
        self.conversation_store = get_conversation_store()

        # Intent Router (lazy)
        self._intent_router: IntentRouterAgent | None = None

        # Enricher Registry - SIN IF/ELSE
        self._enricher_registry: EnricherRegistry | None = None

        # Palabras de confirmación/rechazo para contexto
        self.confirm_words = ["sí", "si", "ok", "okay", "dale", "perfecto", "listo", "adelante", "correcto"]
        self.reject_words = ["no", "mejor no", "cancela", "cancelar", "olvídalo", "dejalo", "nada"]

    @property
    def intent_router(self) -> IntentRouterAgent:
        if self._intent_router is None:
            self._intent_router = get_intent_router()
        return self._intent_router

    @property
    def enricher_registry(self) -> EnricherRegistry:
        if self._enricher_registry is None:
            self._enricher_registry = get_enricher_registry()
            # Registrar todos los enrichers al inicializar
            register_all_enrichers()
            stats = self._enricher_registry.get_stats()
            self.logger.info(f"EnricherRegistry inicializado: {stats}")
        return self._enricher_registry

    async def process_message(
        self,
        user_id: int,
        message: str,
    ) -> OrchestratorResponse:
        """
        Procesa un mensaje del usuario.

        Flujo:
        1. Verificar contexto conversacional
        2. Clasificar intención (IntentRouter)
        3. Enriquecer con EnricherRegistry (SIN IF/ELSE)
        4. Retornar respuesta

        Args:
            user_id: ID del usuario de Telegram
            message: Mensaje del usuario

        Returns:
            OrchestratorResponse con toda la información procesada
        """
        start_time = datetime.now()
        agents_used = []

        # 1. Obtener contexto conversacional
        ctx = self.conversation_store.get(user_id)

        # 2. Verificar si es respuesta rápida (sí/no)
        quick_response = self._check_quick_response(message, ctx)
        if quick_response:
            self.conversation_store.save(ctx)
            return quick_response

        # 3. Verificar si es acción contextual
        if ctx.active_entity or ctx.pending_action:
            contextual = await self._process_contextual(message, ctx)
            if contextual:
                self.conversation_store.save(ctx)
                return contextual

        # 4. Clasificar intención
        agents_used.append("IntentRouter")
        intent_result = await self.intent_router.execute(
            message=message,
            conversation_context=ctx.get_history_summary(),
        )

        # 5. Enriquecer usando EnricherRegistry (SIN IF/ELSE!)
        enrichment = await self.enricher_registry.enrich(
            intent=intent_result.intent,
            message=message,
            entities=intent_result.entities,
            context={"user_id": user_id, "conversation": ctx.get_history_summary()},
        )

        if enrichment:
            agents_used.extend(enrichment.agents_used)

        # 6. Agregar al historial
        ctx.add_message(
            role="user",
            content=message,
            intent=intent_result.intent.value,
            entities=intent_result.entities,
        )

        # 7. Construir respuesta
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        response = OrchestratorResponse(
            message="",  # Se llenará por el handler
            intent=intent_result.intent,
            enrichment=enrichment,
            entities=intent_result.entities,
            confidence=intent_result.confidence,
            is_contextual=False,
            processing_time_ms=processing_time,
            agents_used=agents_used,
        )

        # 8. Guardar contexto
        self.conversation_store.save(ctx)

        return response

    def _check_quick_response(
        self,
        message: str,
        ctx: ConversationContext,
    ) -> OrchestratorResponse | None:
        """Verifica si es una respuesta rápida de confirmación/rechazo."""
        message_lower = message.lower().strip()

        if not ctx.pending_action or ctx.pending_action.is_expired():
            return None

        # Confirmación
        if any(word in message_lower for word in self.confirm_words):
            return self._handle_confirmation(ctx)

        # Rechazo
        if any(word in message_lower for word in self.reject_words):
            return self._handle_rejection(ctx)

        return None

    def _handle_confirmation(self, ctx: ConversationContext) -> OrchestratorResponse:
        """Maneja confirmación de acción pendiente."""
        action = ctx.pending_action

        if action.action_type == "create_subtasks":
            subtasks = action.data.get("subtasks", [])
            ctx.active_entity.subtasks = subtasks
            ctx.clear_pending_action()
            ctx.state = ConversationState.IDLE

            return OrchestratorResponse(
                message=f"Subtareas añadidas:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(subtasks)),
                intent=UserIntent.TASK_CREATE,
                is_contextual=True,
                already_handled=True,
            )

        elif action.action_type == "delete_entity":
            entity_name = ctx.active_entity.entity_name if ctx.active_entity else "elemento"
            ctx.clear_active_entity()
            ctx.clear_pending_action()

            return OrchestratorResponse(
                message=f"{entity_name} eliminado.",
                intent=UserIntent.TASK_DELETE,
                is_contextual=True,
                already_handled=True,
            )

        ctx.clear_pending_action()
        return OrchestratorResponse(
            message="Acción completada.",
            intent=UserIntent.UNKNOWN,
            is_contextual=True,
            already_handled=True,
        )

    def _handle_rejection(self, ctx: ConversationContext) -> OrchestratorResponse:
        """Maneja rechazo de acción pendiente."""
        ctx.clear_pending_action()
        ctx.state = ConversationState.IDLE

        return OrchestratorResponse(
            message="Entendido, cancelado.",
            intent=UserIntent.UNKNOWN,
            is_contextual=True,
            already_handled=True,
        )

    async def _process_contextual(
        self,
        message: str,
        ctx: ConversationContext,
    ) -> OrchestratorResponse | None:
        """Procesa mensaje en contexto de entidad activa."""
        import re
        from app.services.notion import get_notion_service

        msg_lower = message.lower()

        # Solo procesar si hay una tarea activa
        if not ctx.active_entity or ctx.active_entity.entity_type != EntityType.TASK:
            return None

        task_id = ctx.active_entity.entity_id
        task_name = ctx.active_entity.entity_name

        # Detectar modificación de subtareas: "quita la 3"
        remove_match = re.search(r"(?:quita|elimina|borra)\s+(?:la|el)?\s*(\d+)", msg_lower)
        if remove_match and ctx.active_entity.suggested_subtasks:
            idx = int(remove_match.group(1))
            subtasks = ctx.active_entity.suggested_subtasks

            if 1 <= idx <= len(subtasks):
                removed = subtasks.pop(idx - 1)
                ctx.active_entity.suggested_subtasks = subtasks

                msg_parts = [f"Quitada: {removed}", "\nSubtareas actualizadas:"]
                for i, s in enumerate(subtasks, 1):
                    msg_parts.append(f"  {i}. {s}")

                return OrchestratorResponse(
                    message="\n".join(msg_parts),
                    intent=UserIntent.TASK_UPDATE,
                    is_contextual=True,
                    already_handled=True,
                )

        # Detectar asignación de proyecto: "añádela al proyecto X", "ponla en proyecto X"
        project_match = re.search(
            r"(?:añ[aá]de(?:la|lo)?|pon(?:la|lo)?|asign[aá](?:la|lo)?|mueve(?:la|lo)?|agr[eé]ga(?:la|lo)?)\s+(?:al?|en|a)\s+(?:el\s+)?(?:proyecto\s+)?(.+)",
            msg_lower
        )
        if project_match and task_id:
            project_name_query = project_match.group(1).strip()
            # Limpiar palabras comunes
            project_name_query = re.sub(r"^(el|la|los|las)\s+", "", project_name_query)

            # Buscar el proyecto
            notion = get_notion_service()
            raw_projects = await notion.get_projects(active_only=True, use_cache=False)

            found_project = None
            for raw_project in raw_projects:
                try:
                    title_prop = raw_project.get("properties", {}).get("Proyecto", {})
                    title_list = title_prop.get("title", [])
                    name = title_list[0].get("plain_text", "") if title_list else ""

                    if project_name_query.lower() in name.lower() or name.lower() in project_name_query.lower():
                        found_project = {
                            "id": raw_project.get("id"),
                            "name": name,
                        }
                        break
                except (KeyError, IndexError):
                    continue

            if found_project:
                # Actualizar la tarea en Notion
                try:
                    await notion.client.pages.update(
                        page_id=task_id,
                        properties={
                            "Proyecto": {"relation": [{"id": found_project["id"]}]}
                        }
                    )

                    # Actualizar contexto
                    ctx.active_entity.entity_data["project_id"] = found_project["id"]
                    ctx.active_entity.entity_data["project_name"] = found_project["name"]

                    return OrchestratorResponse(
                        message=f"✅ <b>Proyecto asignado</b>\n\n<i>{task_name}</i>\n📁 {found_project['name']}",
                        intent=UserIntent.TASK_UPDATE,
                        is_contextual=True,
                        already_handled=True,
                    )
                except Exception as e:
                    logger.error(f"Error asignando proyecto: {e}")
            else:
                # Listar proyectos disponibles
                project_names = []
                for rp in raw_projects[:5]:
                    try:
                        tp = rp.get("properties", {}).get("Proyecto", {})
                        tl = tp.get("title", [])
                        pn = tl[0].get("plain_text", "") if tl else ""
                        if pn:
                            project_names.append(f"• {pn}")
                    except:
                        pass

                projects_list = "\n".join(project_names) if project_names else "No hay proyectos activos"

                return OrchestratorResponse(
                    message=f"❌ No encontré el proyecto \"{project_name_query}\".\n\n<b>Proyectos disponibles:</b>\n{projects_list}",
                    intent=UserIntent.TASK_UPDATE,
                    is_contextual=True,
                    already_handled=True,
                )

        # Detectar cambio de prioridad: "ponla urgente", "hazla alta prioridad"
        priority_match = re.search(
            r"(?:pon(?:la|lo)?|haz(?:la|lo)?|cambia(?:la|lo)?|marca(?:la|lo)?)\s+(?:como\s+)?(?:a\s+)?(?:prioridad\s+)?(urgente|alta|normal|baja)",
            msg_lower
        )
        if priority_match and task_id:
            priority_str = priority_match.group(1)
            priority_map = {
                "urgente": "Urgente",
                "alta": "Alta",
                "normal": "Normal",
                "baja": "Baja",
            }
            notion_priority = priority_map.get(priority_str, "Normal")

            try:
                notion = get_notion_service()
                await notion.client.pages.update(
                    page_id=task_id,
                    properties={
                        "Prioridad": {"select": {"name": notion_priority}}
                    }
                )

                emoji_map = {"Urgente": "🔥", "Alta": "⚡", "Normal": "🔄", "Baja": "🧊"}

                return OrchestratorResponse(
                    message=f"✅ <b>Prioridad actualizada</b>\n\n<i>{task_name}</i>\n{emoji_map.get(notion_priority, '')} {notion_priority}",
                    intent=UserIntent.TASK_UPDATE,
                    is_contextual=True,
                    already_handled=True,
                )
            except Exception as e:
                logger.error(f"Error cambiando prioridad: {e}")

        # Detectar inicio de tarea: "empieza", "hazla", "trabaja en ella"
        start_match = re.search(r"^(?:empieza|empezar|empié?zala|trabaja|inicia(?:la)?|comienza)(?:\s|$)", msg_lower)
        if start_match and task_id:
            try:
                notion = get_notion_service()
                await notion.client.pages.update(
                    page_id=task_id,
                    properties={
                        "Estado": {"select": {"name": "Doing"}}
                    }
                )

                return OrchestratorResponse(
                    message=f"▶️ <b>Tarea iniciada</b>\n\n<i>{task_name}</i>\n\n¡A trabajar! 💪",
                    intent=UserIntent.TASK_STATUS_CHANGE,
                    is_contextual=True,
                    already_handled=True,
                )
            except Exception as e:
                logger.error(f"Error iniciando tarea: {e}")

        return None


# Singleton
_unified_orchestrator: UnifiedOrchestrator | None = None


def get_unified_orchestrator() -> UnifiedOrchestrator:
    """Obtiene la instancia del orquestador unificado."""
    global _unified_orchestrator
    if _unified_orchestrator is None:
        _unified_orchestrator = UnifiedOrchestrator()
    return _unified_orchestrator


# Reset para testing
def reset_orchestrator() -> None:
    """Resetea el orquestador (útil para tests)."""
    global _unified_orchestrator
    _unified_orchestrator = None
