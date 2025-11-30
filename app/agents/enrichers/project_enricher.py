"""
Project Enricher - Enriquece intents de proyectos.

Integra búsqueda de proyectos existentes y sugerencias.
"""

import logging
import re
from typing import Any

from app.agents.enrichers.base import BaseEnricher, EnrichmentResult
from app.agents.intent_router import UserIntent

logger = logging.getLogger(__name__)


class ProjectEnricher(BaseEnricher):
    """Enricher para proyectos."""

    name = "ProjectEnricher"
    intents = [
        UserIntent.PROJECT_CREATE,
        UserIntent.PROJECT_UPDATE,
        UserIntent.PROJECT_DELETE,
        UserIntent.PROJECT_QUERY,
    ]

    # Tipos de proyecto conocidos
    project_type_keywords = {
        "trabajo": ["trabajo", "work", "paycash", "oficina", "netsuite"],
        "freelance": ["freelance", "cliente", "workana", "upwork"],
        "personal": ["personal", "casa", "propio", "hobby"],
        "estudio": ["estudio", "aprender", "curso", "tutorial", "certificación"],
        "side_project": ["side project", "side-project", "experimento", "startup"],
    }

    async def enrich(
        self,
        intent: UserIntent,
        message: str,
        entities: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EnrichmentResult:
        """Enriquece intent de proyecto."""
        result = EnrichmentResult(enricher_name=self.name)

        # Extraer nombre del proyecto
        project_name = entities.get("project_name") or self._extract_project_name(message)

        # Detectar tipo de proyecto
        project_type = entities.get("project_type") or self._detect_project_type(message)

        result.project_match = {
            "name": project_name,
            "type": project_type,
            "intent": intent.value,
        }

        if intent == UserIntent.PROJECT_CREATE:
            # Sugerir estructura inicial
            result.project_suggestions = self._suggest_initial_tasks(project_name, project_type)

        return result

    def _extract_project_name(self, message: str) -> str | None:
        """Extrae nombre del proyecto del mensaje."""
        patterns = [
            r'(?:crear|nuevo|iniciar)\s+proyecto\s+["\']?([^"\',-]+)["\']?',
            r'proyecto\s+["\']?([^"\',-]+)["\']?',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _detect_project_type(self, message: str) -> str:
        """Detecta tipo de proyecto del mensaje."""
        message_lower = message.lower()

        for project_type, keywords in self.project_type_keywords.items():
            if any(kw in message_lower for kw in keywords):
                return project_type

        return "personal"

    def _suggest_initial_tasks(self, name: str, project_type: str) -> list[str]:
        """Sugiere tareas iniciales para un proyecto."""
        common_tasks = [
            "Definir objetivo y alcance",
            "Crear estructura de carpetas",
            "Configurar herramientas",
        ]

        type_specific = {
            "trabajo": [
                "Alinear con stakeholders",
                "Crear documentación inicial",
                "Definir milestones",
            ],
            "freelance": [
                "Acordar entregables con cliente",
                "Establecer timeline",
                "Configurar facturación",
            ],
            "estudio": [
                "Definir temario",
                "Establecer horario de estudio",
                "Buscar recursos",
            ],
            "side_project": [
                "Validar idea",
                "Crear MVP mínimo",
                "Buscar early users",
            ],
        }

        tasks = common_tasks + type_specific.get(project_type, [])
        return tasks[:5]
