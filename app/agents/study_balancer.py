"""StudyBalancer Agent - Sugiere qué estudiar basado en balance y progreso."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

import dspy

from app.agents.base import setup_dspy

logger = logging.getLogger(__name__)


class EnergyLevel(str, Enum):
    """Nivel de energía del usuario."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestStudyTopic(dspy.Signature):
    """Sugiere qué tema estudiar basado en balance y contexto."""

    study_projects: str = dspy.InputField(
        desc="Lista de proyectos de estudio con progreso y última actividad"
    )
    recent_sessions: str = dspy.InputField(
        desc="Sesiones de estudio de la última semana"
    )
    project_deadlines: str = dspy.InputField(
        desc="Deadlines de proyectos si los hay"
    )
    user_preference: str = dspy.InputField(
        desc="Si el usuario pidió algo específico, o vacío"
    )
    energy_level: str = dspy.InputField(
        desc="Nivel de energía: high, medium, low"
    )
    day_of_week: str = dspy.InputField(
        desc="Día de la semana actual"
    )

    suggested_topic: str = dspy.OutputField(
        desc="Tema sugerido para estudiar"
    )
    suggestion_reason: str = dspy.OutputField(
        desc="Por qué se sugiere este tema"
    )
    alternative_topic: str = dspy.OutputField(
        desc="Alternativa si no quiere el sugerido"
    )
    balance_status: str = dspy.OutputField(
        desc="Estado del balance entre temas (bueno, desbalanceado, etc.)"
    )
    neglected_topics: str = dspy.OutputField(
        desc="Temas sin estudiar hace tiempo, separados por coma"
    )
    session_goal: str = dspy.OutputField(
        desc="Objetivo específico para la sesión de hoy"
    )


@dataclass
class StudyProject:
    """Representa un proyecto de estudio."""

    id: str
    name: str
    current_milestone: str
    progress: int  # 0-100
    last_activity: datetime | None
    days_inactive: int
    in_rotation: bool = True


@dataclass
class StudySession:
    """Representa una sesión de estudio."""

    date: datetime
    topic: str
    duration_minutes: int
    notes: str = ""


@dataclass
class StudySuggestionResult:
    """Resultado de la sugerencia de estudio."""

    topic: str
    project_id: str | None
    reason: str
    alternative: str | None
    balance_status: str
    neglected_topics: list[str]
    session_goal: str
    estimated_duration: int = 60  # minutos


class StudyBalancerAgent:
    """Agente para sugerir temas de estudio balanceados."""

    def __init__(self):
        setup_dspy()
        self.suggester = dspy.ChainOfThought(SuggestStudyTopic)

        # Proyectos de estudio de Carlos (de Documentacion.MD)
        self.default_projects = [
            StudyProject(
                id="video_editing",
                name="Edición de Video (Premiere)",
                current_milestone="Curso básico",
                progress=30,
                last_activity=None,
                days_inactive=0,
            ),
            StudyProject(
                id="dspy_ai",
                name="DSPy / AI Agents",
                current_milestone="Implementar primer agente",
                progress=20,
                last_activity=None,
                days_inactive=0,
            ),
            StudyProject(
                id="netsuite",
                name="NetSuite Avanzado",
                current_milestone="SuiteScript 2.0",
                progress=50,
                last_activity=None,
                days_inactive=0,
            ),
        ]

        # Reglas de rotación
        self.max_consecutive_days = 3
        self.balance_threshold_days = 5  # Días sin estudiar = descuidado

    async def suggest_topic(
        self,
        projects: list[StudyProject] | None = None,
        recent_sessions: list[StudySession] | None = None,
        user_preference: str = "",
        energy_level: EnergyLevel = EnergyLevel.MEDIUM,
    ) -> StudySuggestionResult:
        """
        Sugiere un tema de estudio.

        Args:
            projects: Lista de proyectos de estudio
            recent_sessions: Sesiones de la última semana
            user_preference: Si el usuario pidió algo específico
            energy_level: Nivel de energía actual

        Returns:
            StudySuggestionResult con la sugerencia
        """
        if projects is None:
            projects = self.default_projects

        if recent_sessions is None:
            recent_sessions = []

        try:
            # Calcular días inactivos para cada proyecto
            self._update_inactivity(projects, recent_sessions)

            # Formatear info para el LLM
            projects_str = self._format_projects(projects)
            sessions_str = self._format_sessions(recent_sessions)
            deadlines_str = self._get_deadlines(projects)

            now = datetime.now()
            day_names = {
                0: "Lunes",
                1: "Martes",
                2: "Miércoles",
                3: "Jueves",
                4: "Viernes",
                5: "Sábado",
                6: "Domingo",
            }
            day_of_week = day_names.get(now.weekday(), "Lunes")

            # Obtener sugerencia del LLM
            result = self.suggester(
                study_projects=projects_str,
                recent_sessions=sessions_str,
                project_deadlines=deadlines_str,
                user_preference=user_preference or "Sin preferencia específica",
                energy_level=energy_level.value,
                day_of_week=day_of_week,
            )

            # Encontrar proyecto correspondiente
            project_id = None
            for project in projects:
                if project.name.lower() in str(result.suggested_topic).lower():
                    project_id = project.id
                    break

            # Parsear neglected topics
            neglected = [
                t.strip()
                for t in str(result.neglected_topics).split(",")
                if t.strip()
            ]

            # Determinar duración basada en energía
            duration_map = {
                EnergyLevel.HIGH: 90,
                EnergyLevel.MEDIUM: 60,
                EnergyLevel.LOW: 30,
            }

            return StudySuggestionResult(
                topic=str(result.suggested_topic),
                project_id=project_id,
                reason=str(result.suggestion_reason),
                alternative=str(result.alternative_topic) if result.alternative_topic else None,
                balance_status=str(result.balance_status),
                neglected_topics=neglected[:3],
                session_goal=str(result.session_goal),
                estimated_duration=duration_map.get(energy_level, 60),
            )

        except Exception as e:
            logger.error(f"Error sugiriendo tema de estudio: {e}")
            return self._create_fallback_suggestion(projects, energy_level)

    def _update_inactivity(
        self,
        projects: list[StudyProject],
        sessions: list[StudySession],
    ) -> None:
        """Actualiza los días de inactividad de cada proyecto."""
        now = datetime.now()

        # Crear mapa de última actividad por proyecto
        last_activity_map = {}
        for session in sessions:
            topic_lower = session.topic.lower()
            for project in projects:
                if project.name.lower() in topic_lower or topic_lower in project.name.lower():
                    current_last = last_activity_map.get(project.id)
                    if current_last is None or session.date > current_last:
                        last_activity_map[project.id] = session.date

        # Actualizar proyectos
        for project in projects:
            last = last_activity_map.get(project.id)
            if last:
                project.last_activity = last
                project.days_inactive = (now - last).days
            else:
                project.days_inactive = 999  # Nunca estudiado

    def _format_projects(self, projects: list[StudyProject]) -> str:
        """Formatea proyectos para el LLM."""
        lines = []
        for p in projects:
            if not p.in_rotation:
                continue

            inactive_str = (
                f"hace {p.days_inactive} días"
                if p.days_inactive < 999
                else "nunca estudiado"
            )
            lines.append(
                f"- {p.name}: {p.progress}% completado, "
                f"hito: '{p.current_milestone}', "
                f"última actividad: {inactive_str}"
            )
        return "\n".join(lines) if lines else "Sin proyectos de estudio"

    def _format_sessions(self, sessions: list[StudySession]) -> str:
        """Formatea sesiones recientes para el LLM."""
        if not sessions:
            return "Sin sesiones recientes"

        lines = []
        for s in sessions[-7:]:  # Últimas 7 sesiones
            date_str = s.date.strftime("%d/%m")
            lines.append(f"- {date_str}: {s.topic} ({s.duration_minutes} min)")

        return "\n".join(lines)

    def _get_deadlines(self, projects: list[StudyProject]) -> str:
        """Obtiene deadlines de proyectos."""
        # En esta implementación, no tenemos deadlines
        # Podría extenderse para incluirlos
        return "Sin deadlines urgentes"

    def _create_fallback_suggestion(
        self,
        projects: list[StudyProject],
        energy_level: EnergyLevel,
    ) -> StudySuggestionResult:
        """Crea sugerencia de fallback."""
        # Encontrar proyecto más descuidado
        active_projects = [p for p in projects if p.in_rotation]
        if not active_projects:
            return StudySuggestionResult(
                topic="No hay proyectos de estudio configurados",
                project_id=None,
                reason="Agrega proyectos de estudio en Notion",
                alternative=None,
                balance_status="Sin proyectos",
                neglected_topics=[],
                session_goal="Configurar proyectos de estudio",
                estimated_duration=30,
            )

        # Ordenar por días inactivos
        most_neglected = sorted(
            active_projects,
            key=lambda x: x.days_inactive,
            reverse=True,
        )[0]

        duration = 60 if energy_level != EnergyLevel.LOW else 30

        return StudySuggestionResult(
            topic=most_neglected.name,
            project_id=most_neglected.id,
            reason=f"Hace {most_neglected.days_inactive} días sin actividad",
            alternative=active_projects[1].name if len(active_projects) > 1 else None,
            balance_status="Necesita atención",
            neglected_topics=[most_neglected.name],
            session_goal=f"Avanzar en: {most_neglected.current_milestone}",
            estimated_duration=duration,
        )

    def analyze_balance(
        self,
        projects: list[StudyProject],
        sessions: list[StudySession],
    ) -> dict:
        """
        Analiza el balance de estudio entre proyectos.

        Returns:
            Dict con análisis de balance
        """
        self._update_inactivity(projects, sessions)

        # Contar sesiones por proyecto
        session_counts = {}
        for session in sessions:
            topic_lower = session.topic.lower()
            for project in projects:
                if project.name.lower() in topic_lower:
                    session_counts[project.name] = session_counts.get(project.name, 0) + 1
                    break

        # Calcular balance
        active_projects = [p for p in projects if p.in_rotation]
        total_sessions = sum(session_counts.values())

        balance = {
            "total_sessions": total_sessions,
            "by_project": session_counts,
            "neglected": [
                p.name for p in active_projects
                if p.days_inactive > self.balance_threshold_days
            ],
            "overdue": [
                p.name for p in active_projects
                if session_counts.get(p.name, 0) > self.max_consecutive_days
            ],
            "is_balanced": True,
        }

        # Determinar si está balanceado
        if len(balance["neglected"]) > 0:
            balance["is_balanced"] = False
            balance["recommendation"] = f"Dedica tiempo a: {', '.join(balance['neglected'])}"
        elif active_projects and total_sessions > 0:
            # Verificar distribución
            avg = total_sessions / len(active_projects)
            for name, count in session_counts.items():
                if count > avg * 2:
                    balance["is_balanced"] = False
                    balance["recommendation"] = f"Demasiado enfocado en {name}"
                    break

        if balance["is_balanced"]:
            balance["recommendation"] = "¡Buen balance de estudio!"

        return balance

    def format_telegram_message(self, result: StudySuggestionResult) -> str:
        """Formatea la sugerencia como mensaje de Telegram."""
        message = "📚 <b>Sugerencia de Estudio</b>\n\n"

        message += f"<b>Tema:</b> {result.topic}\n"
        message += f"<i>{result.reason}</i>\n\n"

        message += f"<b>🎯 Meta de sesión:</b>\n{result.session_goal}\n\n"

        message += f"<b>⏱️ Duración sugerida:</b> {result.estimated_duration} min\n"

        if result.alternative:
            message += f"\n<b>📋 Alternativa:</b> {result.alternative}\n"

        if result.neglected_topics:
            message += f"\n<b>⚠️ Descuidados:</b> {', '.join(result.neglected_topics)}\n"

        message += f"\n<b>📊 Balance:</b> {result.balance_status}"

        return message

    def get_weekly_study_stats(
        self,
        sessions: list[StudySession],
    ) -> dict:
        """Obtiene estadísticas de estudio de la semana."""
        week_ago = datetime.now() - timedelta(days=7)
        week_sessions = [s for s in sessions if s.date >= week_ago]

        total_minutes = sum(s.duration_minutes for s in week_sessions)
        total_sessions = len(week_sessions)

        by_day = {}
        for session in week_sessions:
            day = session.date.strftime("%A")
            by_day[day] = by_day.get(day, 0) + session.duration_minutes

        return {
            "total_sessions": total_sessions,
            "total_hours": round(total_minutes / 60, 1),
            "avg_per_session": round(total_minutes / total_sessions, 0) if total_sessions > 0 else 0,
            "by_day": by_day,
            "streak": self._calculate_streak(sessions),
        }

    def _calculate_streak(self, sessions: list[StudySession]) -> int:
        """Calcula la racha de días consecutivos de estudio."""
        if not sessions:
            return 0

        # Ordenar por fecha descendente
        sorted_sessions = sorted(sessions, key=lambda x: x.date, reverse=True)

        streak = 0
        current_date = datetime.now().date()

        for session in sorted_sessions:
            session_date = session.date.date()

            if session_date == current_date:
                streak = 1
                current_date = current_date - timedelta(days=1)
            elif session_date == current_date:
                current_date = current_date - timedelta(days=1)
            else:
                break

        return streak
