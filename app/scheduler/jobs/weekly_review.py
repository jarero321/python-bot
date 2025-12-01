"""Weekly Review Job - Revisión semanal los domingos."""

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.services.telegram import get_telegram_service
from app.services.notion import get_notion_service, TaskEstado

logger = logging.getLogger(__name__)
settings = get_settings()


async def weekly_review_job() -> None:
    """
    Envía revisión semanal con métricas y análisis.

    Se ejecuta los domingos a las 10:00 AM.
    """
    logger.info("Ejecutando Weekly Review...")

    telegram = get_telegram_service()
    notion = get_notion_service()

    try:
        # Recopilar métricas de la semana
        metrics = await _gather_weekly_metrics(notion)

        # Generar mensaje
        message = _format_weekly_review(metrics)

        await telegram.send_message(text=message)

        logger.info("Weekly Review enviado")

    except Exception as e:
        logger.error(f"Error en Weekly Review: {e}")


async def _gather_weekly_metrics(notion) -> dict:
    """Recopila métricas de la semana."""
    metrics = {
        "tasks_completed": 0,
        "tasks_by_context": {},
        "gym_sessions": 0,
        "gym_by_type": {},
        "nutrition_days_logged": 0,
        "nutrition_avg_rating": "?",
        "transactions_count": 0,
        "total_spent": 0.0,
        "total_income": 0.0,
    }

    try:
        # Tareas completadas esta semana
        tasks_done = await notion.get_tasks_by_estado(TaskEstado.DONE, limit=50)
        week_ago = datetime.now() - timedelta(days=7)

        for task in tasks_done:
            props = task.get("properties", {})
            fecha_done = props.get("Fecha Done", {}).get("date", {})
            if fecha_done:
                done_date_str = fecha_done.get("start", "")
                if done_date_str:
                    try:
                        done_date = datetime.fromisoformat(done_date_str.split("T")[0])
                        if done_date >= week_ago:
                            metrics["tasks_completed"] += 1

                            # Por contexto
                            contexto = props.get("Contexto", {}).get("select", {})
                            ctx_name = contexto.get("name", "Otro") if contexto else "Otro"
                            metrics["tasks_by_context"][ctx_name] = (
                                metrics["tasks_by_context"].get(ctx_name, 0) + 1
                            )
                    except ValueError:
                        pass

        # Sesiones de gym
        workouts = await notion.get_workout_history(weeks=1)
        for workout in workouts:
            props = workout.get("properties", {})
            completado = props.get("Completado", {}).get("checkbox", False)
            if completado:
                metrics["gym_sessions"] += 1

                tipo = props.get("Tipo", {}).get("select", {})
                tipo_name = tipo.get("name", "Otro") if tipo else "Otro"
                metrics["gym_by_type"][tipo_name] = (
                    metrics["gym_by_type"].get(tipo_name, 0) + 1
                )

        # Nutrición
        nutrition = await notion.get_nutrition_history(days=7)
        metrics["nutrition_days_logged"] = len(nutrition)

        ratings = []
        for day in nutrition:
            props = day.get("properties", {})
            evaluacion = props.get("Evaluación", {}).get("select", {})
            if evaluacion:
                rating = evaluacion.get("name", "")
                if "Buen" in rating:
                    ratings.append(3)
                elif "Regular" in rating:
                    ratings.append(2)
                elif "Mejorable" in rating:
                    ratings.append(1)

        if ratings:
            avg = sum(ratings) / len(ratings)
            if avg >= 2.5:
                metrics["nutrition_avg_rating"] = "🟢 Bueno"
            elif avg >= 1.5:
                metrics["nutrition_avg_rating"] = "🟡 Regular"
            else:
                metrics["nutrition_avg_rating"] = "🔴 Mejorable"

        # Finanzas
        transactions = await notion.get_transactions(limit=100)
        for tx in transactions:
            props = tx.get("properties", {})
            fecha = props.get("Fecha", {}).get("date", {})
            if fecha:
                tx_date_str = fecha.get("start", "")
                if tx_date_str:
                    try:
                        tx_date = datetime.fromisoformat(tx_date_str.split("T")[0])
                        if tx_date >= week_ago:
                            metrics["transactions_count"] += 1

                            monto = props.get("Monto", {}).get("number", 0) or 0
                            tipo = props.get("Tipo", {}).get("select", {})
                            tipo_name = tipo.get("name", "") if tipo else ""

                            if "Ingreso" in tipo_name:
                                metrics["total_income"] += monto
                            else:
                                metrics["total_spent"] += abs(monto)
                    except ValueError:
                        pass

    except Exception as e:
        logger.error(f"Error recopilando métricas: {e}")

    return metrics


def _format_weekly_review(metrics: dict) -> str:
    """Formatea la revisión semanal."""
    now = datetime.now()
    week_start = now - timedelta(days=7)

    message = (
        f"📊 <b>Revisión Semanal</b>\n"
        f"{week_start.strftime('%d/%m')} - {now.strftime('%d/%m/%Y')}\n\n"
    )

    # Tareas
    message += "✅ <b>Productividad</b>\n"
    message += f"• Tareas completadas: {metrics['tasks_completed']}\n"

    if metrics["tasks_by_context"]:
        message += "• Por contexto:\n"
        for ctx, count in sorted(
            metrics["tasks_by_context"].items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            message += f"   - {ctx}: {count}\n"

    message += "\n"

    # Gym
    message += "🏋️ <b>Gym</b>\n"
    target_gym = 5  # 5 días por semana
    gym_emoji = "✅" if metrics["gym_sessions"] >= target_gym else "⚠️"
    message += f"{gym_emoji} Sesiones: {metrics['gym_sessions']}/{target_gym}\n"

    if metrics["gym_by_type"]:
        types_str = ", ".join(
            f"{t}: {c}" for t, c in metrics["gym_by_type"].items()
        )
        message += f"• Tipos: {types_str}\n"

    message += "\n"

    # Nutrición
    message += "🍽️ <b>Nutrición</b>\n"
    nutrition_emoji = "✅" if metrics["nutrition_days_logged"] >= 5 else "⚠️"
    message += f"{nutrition_emoji} Días registrados: {metrics['nutrition_days_logged']}/7\n"
    message += f"• Promedio: {metrics['nutrition_avg_rating']}\n"

    message += "\n"

    # Finanzas
    message += "💰 <b>Finanzas</b>\n"
    message += f"• Ingresos: ${metrics['total_income']:,.2f}\n"
    message += f"• Gastos: ${metrics['total_spent']:,.2f}\n"
    balance = metrics["total_income"] - metrics["total_spent"]
    balance_emoji = "📈" if balance > 0 else "📉"
    message += f"{balance_emoji} Balance: ${balance:,.2f}\n"

    message += "\n"

    # Reflexión
    message += (
        "💭 <b>Reflexión</b>\n"
        "¿Qué funcionó bien esta semana?\n"
        "¿Qué puedo mejorar?\n"
        "¿Cuál es mi foco para la próxima semana?\n"
    )

    message += "\n<i>Responde con tus reflexiones o usa /skip para omitir</i>"

    return message
