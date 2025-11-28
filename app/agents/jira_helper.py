"""JiraHelper Agent - Ayuda a documentar tareas para Jira."""

import logging
from dataclasses import dataclass

import dspy

from app.agents.base import get_dspy_lm

logger = logging.getLogger(__name__)


class GenerateJiraContent(dspy.Signature):
    """Genera contenido formateado para Jira basado en una tarea."""

    task_description: str = dspy.InputField(
        desc="Descripción de la tarea completada o en progreso"
    )
    task_context: str = dspy.InputField(
        desc="Contexto del proyecto (PayCash, Freelance, etc.)"
    )
    time_spent: str = dspy.InputField(
        desc="Tiempo invertido en la tarea (ej: 2h, 30min)"
    )
    blockers_encountered: str = dspy.InputField(
        desc="Blockers o problemas encontrados (vacío si ninguno)"
    )
    next_steps: str = dspy.InputField(
        desc="Próximos pasos o lo que falta (vacío si completada)"
    )

    jira_title: str = dspy.OutputField(
        desc="Título conciso para Jira (máx 80 caracteres)"
    )
    jira_description: str = dspy.OutputField(
        desc="Descripción detallada en formato Jira con secciones"
    )
    suggested_labels: str = dspy.OutputField(
        desc="Labels sugeridos separados por coma (ej: backend, api, bug)"
    )
    story_points: int = dspy.OutputField(
        desc="Story points sugeridos (1, 2, 3, 5, 8, 13)"
    )
    update_comment: str = dspy.OutputField(
        desc="Comentario de actualización para agregar a la tarea existente"
    )


class GenerateUserStory(dspy.Signature):
    """Genera una Historia de Usuario en formato estándar."""

    feature_description: str = dspy.InputField(
        desc="Descripción de la funcionalidad a implementar"
    )
    user_type: str = dspy.InputField(
        desc="Tipo de usuario (admin, usuario, cliente, etc.)"
    )
    business_context: str = dspy.InputField(
        desc="Contexto de negocio y por qué es importante"
    )

    user_story: str = dspy.OutputField(
        desc="Historia de usuario en formato: Como [rol], quiero [acción], para [beneficio]"
    )
    acceptance_criteria: str = dspy.OutputField(
        desc="Criterios de aceptación numerados (Given/When/Then o lista)"
    )
    technical_notes: str = dspy.OutputField(
        desc="Notas técnicas relevantes para el equipo de desarrollo"
    )
    suggested_subtasks: str = dspy.OutputField(
        desc="Subtareas sugeridas separadas por punto y coma"
    )


@dataclass
class JiraContentResult:
    """Resultado de generación de contenido para Jira."""

    title: str
    description: str
    labels: list[str]
    story_points: int
    update_comment: str


@dataclass
class UserStoryResult:
    """Resultado de generación de Historia de Usuario."""

    story: str
    acceptance_criteria: list[str]
    technical_notes: str
    subtasks: list[str]


class JiraHelperAgent:
    """Agente para ayudar con documentación en Jira."""

    def __init__(self):
        self.lm = get_dspy_lm()
        dspy.configure(lm=self.lm)
        self.content_generator = dspy.ChainOfThought(GenerateJiraContent)
        self.story_generator = dspy.ChainOfThought(GenerateUserStory)

    async def generate_jira_content(
        self,
        task_description: str,
        task_context: str = "PayCash",
        time_spent: str = "",
        blockers: str = "",
        next_steps: str = "",
    ) -> JiraContentResult:
        """
        Genera contenido para actualizar/crear un ticket en Jira.

        Args:
            task_description: Descripción de lo que se hizo
            task_context: Contexto del proyecto
            time_spent: Tiempo invertido
            blockers: Blockers encontrados
            next_steps: Próximos pasos

        Returns:
            JiraContentResult con el contenido formateado
        """
        try:
            result = self.content_generator(
                task_description=task_description,
                task_context=task_context,
                time_spent=time_spent or "No especificado",
                blockers_encountered=blockers or "Ninguno",
                next_steps=next_steps or "Tarea completada",
            )

            # Parsear labels
            labels = [
                label.strip()
                for label in str(result.suggested_labels).split(",")
                if label.strip()
            ]

            # Parsear story points
            try:
                story_points = int(result.story_points)
                # Validar que sea un valor válido de Fibonacci
                if story_points not in [1, 2, 3, 5, 8, 13, 21]:
                    story_points = 3  # Default
            except (ValueError, TypeError):
                story_points = 3

            return JiraContentResult(
                title=str(result.jira_title)[:80],  # Limitar longitud
                description=str(result.jira_description),
                labels=labels[:5],  # Máximo 5 labels
                story_points=story_points,
                update_comment=str(result.update_comment),
            )

        except Exception as e:
            logger.error(f"Error generando contenido Jira: {e}")
            return JiraContentResult(
                title=task_description[:80],
                description=f"## Descripción\n{task_description}\n\n## Tiempo\n{time_spent}",
                labels=["pendiente-revision"],
                story_points=3,
                update_comment=f"Update: {task_description[:100]}",
            )

    async def generate_user_story(
        self,
        feature_description: str,
        user_type: str = "usuario",
        business_context: str = "",
    ) -> UserStoryResult:
        """
        Genera una Historia de Usuario en formato estándar.

        Args:
            feature_description: Descripción de la funcionalidad
            user_type: Tipo de usuario
            business_context: Contexto de negocio

        Returns:
            UserStoryResult con la historia formateada
        """
        try:
            result = self.story_generator(
                feature_description=feature_description,
                user_type=user_type,
                business_context=business_context or "Mejorar la experiencia del usuario",
            )

            # Parsear criterios de aceptación
            criteria_text = str(result.acceptance_criteria)
            criteria = []
            for line in criteria_text.split("\n"):
                line = line.strip()
                if line and (
                    line.startswith("-")
                    or line.startswith("*")
                    or line[0].isdigit()
                    or line.lower().startswith("given")
                    or line.lower().startswith("when")
                    or line.lower().startswith("then")
                ):
                    # Limpiar prefijos
                    line = line.lstrip("-*0123456789.) ")
                    if line:
                        criteria.append(line)

            # Parsear subtareas
            subtasks_text = str(result.suggested_subtasks)
            subtasks = [
                s.strip()
                for s in subtasks_text.replace("\n", ";").split(";")
                if s.strip()
            ]

            return UserStoryResult(
                story=str(result.user_story),
                acceptance_criteria=criteria[:10],  # Máximo 10 criterios
                technical_notes=str(result.technical_notes),
                subtasks=subtasks[:8],  # Máximo 8 subtareas
            )

        except Exception as e:
            logger.error(f"Error generando User Story: {e}")
            return UserStoryResult(
                story=f"Como {user_type}, quiero {feature_description}",
                acceptance_criteria=["Criterios por definir"],
                technical_notes="Revisar con el equipo técnico",
                subtasks=[],
            )

    def format_jira_description(self, result: JiraContentResult) -> str:
        """Formatea la descripción para copiar a Jira."""
        return f"""h2. Descripción
{result.description}

h2. Labels
{', '.join(result.labels)}

h2. Story Points
{result.story_points}

----
_Generado con Carlos Command_"""

    def format_user_story(self, result: UserStoryResult) -> str:
        """Formatea la Historia de Usuario para copiar a Jira."""
        criteria_formatted = "\n".join(
            f"* {c}" for c in result.acceptance_criteria
        )
        subtasks_formatted = "\n".join(
            f"[] {s}" for s in result.subtasks
        )

        return f"""h2. Historia de Usuario
{result.story}

h2. Criterios de Aceptación
{criteria_formatted}

h2. Notas Técnicas
{result.technical_notes}

h2. Subtareas Sugeridas
{subtasks_formatted}

----
_Generado con Carlos Command_"""

    def format_telegram_message(self, result: JiraContentResult) -> str:
        """Formatea el resultado como mensaje de Telegram."""
        message = "📋 <b>Contenido para Jira</b>\n\n"

        message += f"<b>Título:</b>\n<code>{result.title}</code>\n\n"

        message += "<b>Descripción:</b>\n"
        # Limitar descripción para Telegram
        desc_preview = result.description[:500]
        if len(result.description) > 500:
            desc_preview += "..."
        message += f"<pre>{desc_preview}</pre>\n\n"

        message += f"<b>Labels:</b> {', '.join(result.labels)}\n"
        message += f"<b>Story Points:</b> {result.story_points}\n\n"

        message += "<b>Comentario de update:</b>\n"
        message += f"<code>{result.update_comment}</code>\n\n"

        message += "<i>Copia el contenido que necesites a Jira</i>"

        return message

    def format_story_telegram(self, result: UserStoryResult) -> str:
        """Formatea la Historia de Usuario para Telegram."""
        message = "📝 <b>Historia de Usuario</b>\n\n"

        message += f"<b>Story:</b>\n{result.story}\n\n"

        message += "<b>Criterios de Aceptación:</b>\n"
        for i, criterion in enumerate(result.acceptance_criteria[:5], 1):
            message += f"  {i}. {criterion}\n"
        if len(result.acceptance_criteria) > 5:
            message += f"  ... y {len(result.acceptance_criteria) - 5} más\n"

        message += f"\n<b>Notas Técnicas:</b>\n{result.technical_notes[:200]}\n"

        if result.subtasks:
            message += "\n<b>Subtareas:</b>\n"
            for subtask in result.subtasks[:4]:
                message += f"  • {subtask}\n"

        return message


async def quick_jira_update(task_name: str, status: str = "done") -> str:
    """
    Genera un comentario rápido de actualización para Jira.

    Args:
        task_name: Nombre de la tarea
        status: Estado (done, in_progress, blocked)

    Returns:
        Comentario formateado para Jira
    """
    status_messages = {
        "done": f"✅ Tarea completada: {task_name}",
        "in_progress": f"🔄 En progreso: {task_name}",
        "blocked": f"🚫 Bloqueado: {task_name} - Requiere atención",
    }

    return status_messages.get(status, f"Update: {task_name}")
