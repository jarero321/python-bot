"""WorkoutLogger Agent - Registra sesiones de gym con comparación de progreso."""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

import dspy

from app.agents.base import get_dspy_lm

logger = logging.getLogger(__name__)


class WorkoutType(str, Enum):
    """Tipos de entrenamiento PPL."""

    PUSH = "Push"
    PULL = "Pull"
    LEGS = "Legs"
    CARDIO = "Cardio"
    REST = "Rest"


class SessionRating(str, Enum):
    """Calificación de la sesión."""

    EXCELLENT = "excellent"
    GOOD = "good"
    NORMAL = "normal"
    POOR = "poor"


class Sensation(str, Enum):
    """Sensación durante el entrenamiento."""

    FUERTE = "fuerte"
    NORMAL = "normal"
    PESADO = "pesado"
    MOLESTIA = "molestia"


@dataclass
class ExerciseSet:
    """Un set de un ejercicio."""

    weight: float
    reps: int
    pr: bool = False


@dataclass
class Exercise:
    """Un ejercicio con sus sets."""

    name: str
    sets: list[ExerciseSet] = field(default_factory=list)
    pr: bool = False
    notes: str = ""


@dataclass
class ProgressComparison:
    """Comparación con sesión anterior."""

    exercise_name: str
    previous_best: str
    current_best: str
    change: str  # "improved", "maintained", "decreased"
    details: str


@dataclass
class WorkoutResult:
    """Resultado del registro de workout."""

    exercises: list[Exercise]
    comparison: list[ProgressComparison]
    new_prs: list[str]
    session_rating: SessionRating
    improvement_count: int
    feedback: str
    next_targets: dict[str, str]


# DSPy Signature para parsear ejercicios
class ParseWorkoutInput(dspy.Signature):
    """Parsea la descripción de un workout a estructura JSON."""

    workout_description: str = dspy.InputField(
        desc="Descripción del workout en texto libre"
    )
    workout_type: str = dspy.InputField(desc="Tipo: Push, Pull, o Legs")

    exercises_json: str = dspy.OutputField(
        desc="JSON array con ejercicios: [{name, sets: [{weight, reps}]}]"
    )
    sensation: str = dspy.OutputField(
        desc="fuerte/normal/pesado/molestia"
    )
    notes: str = dspy.OutputField(
        desc="Observaciones importantes del workout"
    )


class WorkoutLoggerAgent:
    """Agente para registrar y analizar sesiones de gym."""

    def __init__(self):
        self.lm = get_dspy_lm()
        dspy.configure(lm=self.lm)
        self.parser = dspy.ChainOfThought(ParseWorkoutInput)

        # Ejercicios estándar por tipo (de Documentacion.MD)
        self.standard_exercises = {
            WorkoutType.PUSH: [
                "Press Banca",
                "Press Inclinado",
                "Press Militar",
                "Fondos",
                "Extensiones Tríceps",
            ],
            WorkoutType.PULL: [
                "Dominadas",
                "Remo con Barra",
                "Remo Mancuerna",
                "Face Pulls",
                "Curl Bíceps",
            ],
            WorkoutType.LEGS: [
                "Sentadilla",
                "Peso Muerto Rumano",
                "Prensa",
                "Curl Femoral",
                "Pantorrillas",
            ],
        }

    async def log_workout(
        self,
        workout_description: str,
        workout_type: WorkoutType,
        last_session: dict | None = None,
    ) -> WorkoutResult:
        """
        Registra una sesión de entrenamiento.

        Args:
            workout_description: Descripción del workout en texto
            workout_type: Tipo (Push/Pull/Legs)
            last_session: Datos de la última sesión del mismo tipo

        Returns:
            WorkoutResult con ejercicios estructurados y análisis
        """
        try:
            # Parsear la descripción
            result = self.parser(
                workout_description=workout_description,
                workout_type=workout_type.value,
            )

            # Parsear ejercicios del JSON
            exercises = self._parse_exercises_json(result.exercises_json)

            # Si no se pudo parsear, intentar extracción manual
            if not exercises:
                exercises = self._extract_exercises_manual(
                    workout_description, workout_type
                )

            # Comparar con sesión anterior
            comparison = []
            new_prs = []
            improvement_count = 0

            if last_session:
                comparison, new_prs, improvement_count = self._compare_with_previous(
                    exercises, last_session
                )

            # Calcular rating
            session_rating = self._calculate_rating(
                exercises, improvement_count, result.sensation
            )

            # Generar feedback
            feedback = self._generate_feedback(
                exercises,
                session_rating,
                improvement_count,
                result.sensation,
            )

            # Calcular targets para próxima sesión
            next_targets = self._calculate_next_targets(exercises)

            return WorkoutResult(
                exercises=exercises,
                comparison=comparison,
                new_prs=new_prs,
                session_rating=session_rating,
                improvement_count=improvement_count,
                feedback=feedback,
                next_targets=next_targets,
            )

        except Exception as e:
            logger.error(f"Error registrando workout: {e}")
            return self._create_fallback_result(workout_description)

    def _parse_exercises_json(self, json_str: str) -> list[Exercise]:
        """Parsea JSON de ejercicios."""
        exercises = []

        try:
            # Limpiar el JSON
            json_str = json_str.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]

            data = json.loads(json_str)

            if isinstance(data, list):
                for item in data:
                    sets = []
                    for s in item.get("sets", []):
                        sets.append(ExerciseSet(
                            weight=float(s.get("weight", 0)),
                            reps=int(s.get("reps", 0)),
                        ))
                    exercises.append(Exercise(
                        name=item.get("name", "Ejercicio"),
                        sets=sets,
                    ))

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"No se pudo parsear JSON de ejercicios: {e}")

        return exercises

    def _extract_exercises_manual(
        self, description: str, workout_type: WorkoutType
    ) -> list[Exercise]:
        """Extrae ejercicios de forma manual del texto."""
        exercises = []

        # Patrones comunes: "3x8 banca 60kg", "banca 60kg 3x8"
        patterns = [
            # "3x8 en banca con 60kg"
            r"(\d+)x(\d+)\s+(?:en\s+)?([a-záéíóúñ\s]+?)(?:\s+con\s+|\s+)(\d+(?:\.\d+)?)\s*(?:kg|kilos)?",
            # "banca 60kg 3x8"
            r"([a-záéíóúñ\s]+?)\s+(\d+(?:\.\d+)?)\s*(?:kg|kilos)?\s+(\d+)x(\d+)",
            # "hice banca 3 series de 8 con 60"
            r"([a-záéíóúñ\s]+?)\s+(\d+)\s+series?\s+de\s+(\d+)\s+(?:con\s+)?(\d+(?:\.\d+)?)",
        ]

        description_lower = description.lower()

        for pattern in patterns:
            matches = re.findall(pattern, description_lower)
            for match in matches:
                try:
                    if len(match) == 4:
                        # Determinar orden de grupos
                        if match[0].replace(".", "").isdigit():
                            # Formato: sets, reps, nombre, peso
                            sets_count = int(match[0])
                            reps = int(match[1])
                            name = match[2].strip().title()
                            weight = float(match[3])
                        else:
                            # Formato: nombre, peso, sets, reps
                            name = match[0].strip().title()
                            weight = float(match[1])
                            sets_count = int(match[2])
                            reps = int(match[3])

                        sets = [
                            ExerciseSet(weight=weight, reps=reps)
                            for _ in range(sets_count)
                        ]
                        exercises.append(Exercise(name=name, sets=sets))

                except (ValueError, IndexError):
                    continue

        # Si no se encontró nada, buscar ejercicios estándar
        if not exercises:
            standard = self.standard_exercises.get(workout_type, [])
            for exercise_name in standard:
                if exercise_name.lower() in description_lower:
                    exercises.append(Exercise(
                        name=exercise_name,
                        sets=[],
                        notes="Detalles no especificados",
                    ))

        return exercises

    def _compare_with_previous(
        self,
        current_exercises: list[Exercise],
        last_session: dict,
    ) -> tuple[list[ProgressComparison], list[str], int]:
        """Compara con la sesión anterior."""
        comparisons = []
        new_prs = []
        improvement_count = 0

        # Obtener ejercicios de la sesión anterior
        try:
            previous_data = last_session.get("ejercicios", {})
            if isinstance(previous_data, str):
                previous_data = json.loads(previous_data)
            previous_exercises = previous_data.get("exercises", [])
        except (json.JSONDecodeError, AttributeError):
            previous_exercises = []

        for current in current_exercises:
            # Buscar ejercicio coincidente
            prev_exercise = None
            for prev in previous_exercises:
                if isinstance(prev, dict) and prev.get("name", "").lower() == current.name.lower():
                    prev_exercise = prev
                    break

            if prev_exercise and current.sets:
                # Calcular mejor set actual
                current_best_set = max(
                    current.sets,
                    key=lambda s: s.weight * s.reps if s.weight and s.reps else 0,
                )
                current_best = f"{current_best_set.weight}kg x {current_best_set.reps}"

                # Calcular mejor set anterior
                prev_sets = prev_exercise.get("sets", [])
                if prev_sets:
                    prev_best = max(
                        prev_sets,
                        key=lambda s: s.get("weight", 0) * s.get("reps", 0),
                    )
                    previous_best = f"{prev_best.get('weight', 0)}kg x {prev_best.get('reps', 0)}"

                    # Comparar volumen
                    current_volume = current_best_set.weight * current_best_set.reps
                    prev_volume = prev_best.get("weight", 0) * prev_best.get("reps", 0)

                    if current_volume > prev_volume:
                        change = "improved"
                        improvement_count += 1
                        if current_best_set.weight > prev_best.get("weight", 0):
                            new_prs.append(
                                f"{current.name}: {current_best_set.weight}kg x {current_best_set.reps}"
                            )
                            current.pr = True
                    elif current_volume < prev_volume:
                        change = "decreased"
                    else:
                        change = "maintained"

                    comparisons.append(ProgressComparison(
                        exercise_name=current.name,
                        previous_best=previous_best,
                        current_best=current_best,
                        change=change,
                        details=f"Volumen: {int(current_volume)} vs {int(prev_volume)}",
                    ))

        return comparisons, new_prs, improvement_count

    def _calculate_rating(
        self,
        exercises: list[Exercise],
        improvement_count: int,
        sensation: str,
    ) -> SessionRating:
        """Calcula la calificación de la sesión."""
        # Puntuación base por número de ejercicios
        exercise_score = min(len(exercises) / 5, 1.0)  # 5 ejercicios = 100%

        # Puntuación por mejoras
        improvement_score = min(improvement_count / 3, 1.0)  # 3 mejoras = 100%

        # Puntuación por sensación
        sensation_scores = {
            "fuerte": 1.0,
            "normal": 0.7,
            "pesado": 0.5,
            "molestia": 0.3,
        }
        sensation_score = sensation_scores.get(sensation.lower(), 0.5)

        # Score total
        total = (exercise_score * 0.3 + improvement_score * 0.4 + sensation_score * 0.3)

        if total >= 0.8:
            return SessionRating.EXCELLENT
        elif total >= 0.6:
            return SessionRating.GOOD
        elif total >= 0.4:
            return SessionRating.NORMAL
        else:
            return SessionRating.POOR

    def _generate_feedback(
        self,
        exercises: list[Exercise],
        rating: SessionRating,
        improvement_count: int,
        sensation: str,
    ) -> str:
        """Genera feedback de la sesión."""
        feedbacks = {
            SessionRating.EXCELLENT: "¡Sesión excelente! Sigue así. 💪",
            SessionRating.GOOD: "Buena sesión, mantén la consistencia.",
            SessionRating.NORMAL: "Sesión normal. Cada día cuenta.",
            SessionRating.POOR: "Sesión complicada. Descansa y vuelve más fuerte.",
        }

        feedback = feedbacks.get(rating, "Sesión registrada.")

        if improvement_count > 0:
            feedback += f" Mejoraste en {improvement_count} ejercicio(s)!"

        if sensation.lower() == "molestia":
            feedback += " ⚠️ Revisa la técnica y considera descanso si persiste."

        return feedback

    def _calculate_next_targets(
        self, exercises: list[Exercise]
    ) -> dict[str, str]:
        """Calcula objetivos para la próxima sesión."""
        targets = {}

        for exercise in exercises:
            if exercise.sets:
                # Obtener mejor set
                best_set = max(
                    exercise.sets,
                    key=lambda s: s.weight * s.reps if s.weight and s.reps else 0,
                )

                # Sugerir progresión
                if best_set.reps >= 12:
                    # Aumentar peso
                    new_weight = best_set.weight + 2.5
                    targets[exercise.name] = f"{new_weight}kg x 8-10 reps"
                else:
                    # Aumentar reps
                    new_reps = best_set.reps + 1
                    targets[exercise.name] = f"{best_set.weight}kg x {new_reps} reps"

        return targets

    def _create_fallback_result(self, description: str) -> WorkoutResult:
        """Crea resultado de fallback."""
        return WorkoutResult(
            exercises=[
                Exercise(
                    name="Sesión registrada",
                    sets=[],
                    notes=description[:200],
                )
            ],
            comparison=[],
            new_prs=[],
            session_rating=SessionRating.NORMAL,
            improvement_count=0,
            feedback="Sesión registrada. Agrega más detalles para un mejor análisis.",
            next_targets={},
        )

    def format_telegram_message(self, result: WorkoutResult) -> str:
        """Formatea resultado como mensaje de Telegram."""
        rating_emoji = {
            SessionRating.EXCELLENT: "🌟",
            SessionRating.GOOD: "✅",
            SessionRating.NORMAL: "😐",
            SessionRating.POOR: "😓",
        }

        message = f"🏋️ <b>Sesión de Gym</b> {rating_emoji.get(result.session_rating, '💪')}\n\n"

        # Ejercicios
        message += "<b>📋 Ejercicios:</b>\n"
        for exercise in result.exercises:
            pr_mark = " 🏆 PR!" if exercise.pr else ""
            message += f"• <b>{exercise.name}</b>{pr_mark}\n"
            for i, s in enumerate(exercise.sets, 1):
                message += f"   Set {i}: {s.weight}kg x {s.reps}\n"

        # PRs
        if result.new_prs:
            message += "\n<b>🏆 Nuevos récords:</b>\n"
            for pr in result.new_prs:
                message += f"• {pr}\n"

        # Comparación
        if result.comparison:
            message += "\n<b>📈 Progreso:</b>\n"
            for comp in result.comparison:
                emoji = "📈" if comp.change == "improved" else "📉" if comp.change == "decreased" else "➡️"
                message += f"{emoji} {comp.exercise_name}: {comp.previous_best} → {comp.current_best}\n"

        # Feedback
        message += f"\n<b>💬 Feedback:</b>\n{result.feedback}\n"

        # Próximos targets
        if result.next_targets:
            message += "\n<b>🎯 Próxima sesión:</b>\n"
            for exercise, target in list(result.next_targets.items())[:3]:
                message += f"• {exercise}: {target}\n"

        return message

    def to_notion_json(self, exercises: list[Exercise]) -> str:
        """Convierte ejercicios a JSON para Notion."""
        data = {
            "exercises": [
                {
                    "name": ex.name,
                    "sets": [
                        {"weight": s.weight, "reps": s.reps}
                        for s in ex.sets
                    ],
                    "pr": ex.pr,
                }
                for ex in exercises
            ]
        }
        return json.dumps(data, ensure_ascii=False)
