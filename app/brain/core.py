"""
Carlos Brain - Core del sistema de IA unificado.

Un solo cerebro que procesa todos los triggers y mensajes,
con acceso a tools y memoria contextual.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import google.generativeai as genai

from app.brain.memory import MemoryManager, LongTermMemory
from app.brain.tools import ToolRegistry, ToolResult
from app.brain.prompts import CARLOS_SYSTEM_PROMPT, get_trigger_prompt
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class BrainResponse:
    """Respuesta del Brain después de procesar."""
    message: str | None = None  # Mensaje para el usuario
    keyboard: list[list[dict]] | None = None  # Botones inline
    tools_called: list[str] | None = None  # Tools que se usaron
    action_taken: str | None = None  # Resumen de la acción
    should_save_memory: bool = True  # Si guardar en memoria


class CarlosBrain:
    """
    El cerebro unificado de Carlos.

    Procesa todos los inputs (mensajes de usuario, triggers programados)
    y decide qué hacer usando tools y contexto.

    Uso:
        brain = CarlosBrain(user_id="xxx")
        await brain.initialize()

        # Procesar mensaje de usuario
        response = await brain.process(
            user_message="Crear tarea revisar PRs"
        )

        # Procesar trigger programado
        response = await brain.process(
            trigger="morning_briefing"
        )
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

        # Componentes
        self.memory = MemoryManager(user_id)
        self.long_term = LongTermMemory(user_id)
        self.tools = ToolRegistry(user_id)

        # LLM (Gemini)
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 2048,
            },
            system_instruction=CARLOS_SYSTEM_PROMPT,
        )

        self._initialized = False

    async def initialize(self) -> None:
        """Inicializa el Brain cargando memoria."""
        if self._initialized:
            return

        await self.memory.load()
        self._initialized = True
        logger.info(f"Brain inicializado para user {self.user_id}")

    async def process(
        self,
        user_message: str | None = None,
        trigger: str | None = None,
        context: dict | None = None,
        callback_data: str | None = None,
    ) -> BrainResponse:
        """
        Procesa un input y genera respuesta.

        Args:
            user_message: Mensaje del usuario (si es interacción directa)
            trigger: Tipo de trigger (morning_briefing, gym_check, etc.)
            context: Contexto adicional (task específica, etc.)
            callback_data: Data de callback de botón inline

        Returns:
            BrainResponse con mensaje, keyboard y metadata
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 1. Construir el prompt completo
            prompt = await self._build_prompt(
                user_message=user_message,
                trigger=trigger,
                context=context,
                callback_data=callback_data,
            )

            # 2. Llamar al LLM
            response = await self._call_llm(prompt)

            # 3. Procesar respuesta (ejecutar tools si hay)
            result = await self._process_response(response, original_message=user_message)

            # 4. Guardar en memoria
            if user_message:
                await self.memory.add_message("user", user_message, trigger_type=trigger)
            if result.message:
                await self.memory.add_message(
                    "assistant",
                    result.message,
                    trigger_type=trigger,
                )

            await self.memory.save()

            return result

        except Exception as e:
            logger.exception(f"Error en Brain.process: {e}")
            return BrainResponse(
                message="Lo siento, ocurrió un error. ¿Puedes intentar de nuevo?",
                action_taken=f"error: {str(e)}"
            )

    async def _build_prompt(
        self,
        user_message: str | None,
        trigger: str | None,
        context: dict | None,
        callback_data: str | None,
    ) -> str:
        """Construye el prompt completo para el LLM."""
        parts = []

        # Contexto de memoria
        memory_context = self.memory.get_context_for_llm()
        parts.append(f"## CONTEXTO DE MEMORIA\n{json.dumps(memory_context, indent=2, default=str)}")

        # Contexto temporal
        current_context = await self.tools.execute("get_current_context")
        if current_context.success:
            parts.append(f"## CONTEXTO ACTUAL\n{json.dumps(current_context.data, indent=2)}")

        # Prompt específico del trigger
        if trigger:
            trigger_prompt = get_trigger_prompt(trigger)
            if trigger_prompt:
                parts.append(f"## INSTRUCCIONES DEL TRIGGER ({trigger})\n{trigger_prompt}")

        # Contexto adicional
        if context:
            parts.append(f"## CONTEXTO ADICIONAL\n{json.dumps(context, indent=2, default=str)}")

        # Callback de botón
        if callback_data:
            parts.append(f"## CALLBACK DATA\nEl usuario hizo click en: {callback_data}")

        # Mensaje del usuario
        if user_message:
            parts.append(f"## MENSAJE DEL USUARIO\n{user_message}")
        elif trigger:
            parts.append(f"## TRIGGER\nEste es un trigger automático: {trigger}")

        # Tools disponibles
        tools_schema = self.tools.get_tools_schema()
        parts.append(f"## TOOLS DISPONIBLES\n{json.dumps(tools_schema, indent=2)}")

        # Instrucciones de formato
        parts.append("""
## FORMATO DE RESPUESTA

IMPORTANTE: Debes responder en JSON válido con esta estructura:
{
    "reasoning": "Tu razonamiento interno (breve)",
    "tool_calls": [
        {"tool": "nombre_tool", "args": {...}},
        ...
    ],
    "response": {
        "message": "Mensaje COMPLETO para el usuario (HTML para Telegram)",
        "keyboard": [[{"text": "Botón", "callback_data": "action"}]] o null
    },
    "memory_updates": {
        "active_entity": {"type": "task", "id": "xxx", "title": "yyy"} o null,
        "conversation_mode": "task_management" o null
    }
}

REGLAS CRÍTICAS:
1. NUNCA uses mensajes de "cargando" como "Obteniendo tus tareas..." - siempre da una respuesta FINAL
2. Si no hay tareas, dilo claramente
3. Si hay tareas, formátealas con emojis y estructura clara
4. PROHIBIDO incluir corchetes con texto de botones en el mensaje. Esto está MAL: "[✅ OK] [📝 Editar]"
5. El campo "message" es SOLO texto HTML puro, SIN representación de botones
6. Los botones van ÚNICAMENTE en "keyboard" como array de arrays
7. Máximo 2 botones por fila para que no se corten en móvil

Ejemplo tarea creada (CORRECTO):
{
    "response": {
        "message": "✅ <b>Tarea creada:</b>\\n\\n📋 Revisar código\\n├── 💼 PayCash\\n└── ⏱️ ~30 min",
        "keyboard": [[{"text": "👍", "callback_data": "task_ok"}], [{"text": "📝 Editar", "callback_data": "task_edit"}]]
    }
}

Ejemplo INCORRECTO (NO hacer esto):
{
    "response": {
        "message": "✅ Tarea creada...\\n\\n[✅ OK] [📝 Editar]",
        "keyboard": null
    }
}

Ejemplo cuando NO hay tareas:
{
    "response": {
        "message": "📋 <b>Tareas de hoy</b>\\n\\n✨ No tienes tareas pendientes.",
        "keyboard": [[{"text": "➕ Nueva tarea", "callback_data": "new_task"}]]
    }
}

Si no necesitas enviar mensaje (ej: hourly_pulse sin nada relevante), usa:
{
    "reasoning": "No hay nada relevante que reportar",
    "tool_calls": [],
    "response": null,
    "memory_updates": null
}
""")

        return "\n\n".join(parts)

    async def _call_llm(self, prompt: str) -> dict:
        """Llama al LLM y parsea la respuesta."""
        try:
            response = self.model.generate_content(prompt)
            text = response.text

            # Limpiar markdown si hay
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta del LLM: {e}")
            logger.debug(f"Respuesta raw: {response.text if response else 'None'}")
            # Fallback: intentar extraer mensaje
            return {
                "reasoning": "Error de parseo",
                "tool_calls": [],
                "response": {
                    "message": response.text if response else "Error procesando respuesta",
                    "keyboard": None
                },
                "memory_updates": None
            }

    async def _process_response(self, llm_response: dict, original_message: str | None = None) -> BrainResponse:
        """Procesa la respuesta del LLM, ejecutando tools si necesario."""
        tools_called = []
        tool_results = []

        # Ejecutar tools
        tool_calls = llm_response.get("tool_calls", [])
        for call in tool_calls:
            tool_name = call.get("tool")
            args = call.get("args", {})

            logger.info(f"Ejecutando tool: {tool_name} con args: {args}")
            result = await self.tools.execute(tool_name, **args)
            tools_called.append(tool_name)
            tool_results.append({
                "tool": tool_name,
                "success": result.success,
                "data": result.data,
                "message": result.message,
                "error": result.error
            })

            if not result.success:
                logger.warning(f"Tool {tool_name} falló: {result.error}")

        # Si hay tool_calls, hacer segundo llamado al LLM con los resultados
        if tool_calls and tool_results:
            followup_response = await self._generate_response_with_tool_results(
                original_message or "",
                tool_results
            )
            if followup_response:
                llm_response["response"] = followup_response

        # Actualizar memoria si hay updates
        memory_updates = llm_response.get("memory_updates")
        if memory_updates:
            if memory_updates.get("active_entity"):
                entity = memory_updates["active_entity"]
                self.memory.working.set_active_entity(
                    entity_type=entity["type"],
                    entity_id=entity["id"],
                    title=entity["title"],
                    data=entity.get("data", {})
                )
            if memory_updates.get("conversation_mode"):
                self.memory.working.conversation_mode = memory_updates["conversation_mode"]

        # Construir respuesta
        response_data = llm_response.get("response")

        if response_data is None:
            # No hay mensaje que enviar
            return BrainResponse(
                message=None,
                keyboard=None,
                tools_called=tools_called,
                action_taken=llm_response.get("reasoning"),
                should_save_memory=False
            )

        return BrainResponse(
            message=response_data.get("message"),
            keyboard=response_data.get("keyboard"),
            tools_called=tools_called,
            action_taken=llm_response.get("reasoning")
        )

    async def _generate_response_with_tool_results(
        self,
        original_message: str,
        tool_results: list[dict]
    ) -> dict | None:
        """Genera respuesta final usando los resultados de los tools."""
        prompt = f"""## MENSAJE ORIGINAL DEL USUARIO
{original_message}

## RESULTADOS DE LOS TOOLS EJECUTADOS
{json.dumps(tool_results, indent=2, default=str, ensure_ascii=False)}

## INSTRUCCIONES
Basándote en los resultados de los tools, genera la respuesta para el usuario.

IMPORTANTE:
- Formatea los datos de forma clara y legible
- Usa emojis para mejor visualización
- Si hay tareas, listalas con su prioridad y contexto
- Si no hay tareas, indica que no hay tareas pendientes
- Los botones van en "keyboard", NO como texto

Responde SOLO con JSON:
{{
    "message": "Mensaje HTML formateado para Telegram",
    "keyboard": [[{{"text": "Botón", "callback_data": "action"}}]] o null
}}
"""
        try:
            response = self.model.generate_content(prompt)
            text = response.text

            # Limpiar markdown
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            return json.loads(text.strip())
        except Exception as e:
            logger.error(f"Error generando respuesta con tool results: {e}")
            return None

    # ==================== Métodos de Conveniencia ====================

    async def handle_message(self, text: str) -> BrainResponse:
        """Procesa un mensaje de usuario."""
        return await self.process(user_message=text)

    async def handle_callback(self, callback_data: str) -> BrainResponse:
        """Procesa un callback de botón inline."""
        return await self.process(callback_data=callback_data)

    async def run_trigger(self, trigger: str, context: dict | None = None) -> BrainResponse:
        """Ejecuta un trigger programado."""
        return await self.process(trigger=trigger, context=context)

    async def check_duplicates(self, title: str) -> list[dict]:
        """Verifica duplicados de una tarea."""
        return await self.long_term.find_duplicates(title)

    async def infer_context(self, text: str) -> tuple[str | None, float]:
        """Infiere el contexto de un texto."""
        return await self.long_term.infer_context(text)


# ==================== Singleton ====================

_brain_instances: dict[str, CarlosBrain] = {}


async def get_brain(user_id: str) -> CarlosBrain:
    """Obtiene o crea una instancia del Brain para un usuario."""
    if user_id not in _brain_instances:
        brain = CarlosBrain(user_id)
        await brain.initialize()
        _brain_instances[user_id] = brain

    return _brain_instances[user_id]


def clear_brain_cache() -> None:
    """Limpia el cache de instancias del Brain."""
    _brain_instances.clear()
