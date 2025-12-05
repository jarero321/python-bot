"""Job para sincronizar métricas a Notion como dashboard."""

import logging
from datetime import datetime, timedelta

from app.services.telegram import get_telegram_service
from app.utils.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


async def send_daily_metrics_summary():
    """
    Envía un resumen diario de métricas a Telegram.

    Este job corre una vez al día a las 23:55 para dar
    un resumen del rendimiento del sistema.
    """
    try:
        collector = get_metrics_collector()
        telegram = get_telegram_service()

        summary = collector.get_summary()

        # Formatear mensaje
        message_parts = [
            "📊 <b>Resumen de Métricas del Día</b>",
            "",
            f"⏱️ <b>Uptime:</b> {summary['uptime_human']}",
            "",
            "<b>📡 Endpoints:</b>",
            f"  • Llamadas totales: {summary['endpoints']['total_calls']}",
            f"  • Endpoints únicos: {summary['endpoints']['unique_endpoints']}",
        ]

        # Top endpoints más lentos
        if summary["endpoints"]["slowest"]:
            message_parts.append("  • Más lentos:")
            for ep in summary["endpoints"]["slowest"]:
                message_parts.append(
                    f"    └─ {ep['path']}: {ep['avg_time_ms']:.0f}ms avg"
                )

        message_parts.extend([
            "",
            "<b>🤖 Agentes AI:</b>",
            f"  • Llamadas totales: {summary['agents']['total_calls']}",
            f"  • Tasa de éxito: {summary['agents']['success_rate']}%",
            f"  • Agentes activos: {summary['agents']['unique_agents']}",
        ])

        # Top agentes más lentos
        if summary["agents"]["slowest"]:
            message_parts.append("  • Más lentos:")
            for agent in summary["agents"]["slowest"]:
                message_parts.append(
                    f"    └─ {agent['agent_name']}: {agent['avg_time_ms']:.0f}ms avg"
                )

        message_parts.extend([
            "",
            f"<i>Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>",
        ])

        await telegram.send_message("\n".join(message_parts))
        logger.info("Resumen de métricas enviado")

    except Exception as e:
        logger.error(f"Error enviando resumen de métricas: {e}")


async def send_performance_alert():
    """
    Verifica rendimiento y envía alertas si hay problemas.

    Este job corre cada hora para detectar degradación.
    """
    try:
        collector = get_metrics_collector()
        telegram = get_telegram_service()

        alerts = []

        # Verificar endpoints lentos (>2 segundos promedio)
        for ep in collector.get_endpoint_metrics():
            if ep["avg_time_ms"] > 2000:
                alerts.append(
                    f"⚠️ Endpoint lento: {ep['path']} ({ep['avg_time_ms']:.0f}ms)"
                )
            if ep["error_rate"] > 10:
                alerts.append(
                    f"🔴 Alta tasa de errores: {ep['path']} ({ep['error_rate']}%)"
                )

        # Verificar agentes lentos (>3 segundos promedio)
        for agent in collector.get_agent_metrics():
            if agent["avg_time_ms"] > 3000:
                alerts.append(
                    f"⚠️ Agente lento: {agent['agent_name']} ({agent['avg_time_ms']:.0f}ms)"
                )
            if agent["success_rate"] < 90:
                alerts.append(
                    f"🔴 Baja tasa de éxito: {agent['agent_name']} ({agent['success_rate']}%)"
                )

        if alerts:
            message = (
                "🚨 <b>Alertas de Rendimiento</b>\n\n" +
                "\n".join(alerts) +
                f"\n\n<i>{datetime.now().strftime('%H:%M')}</i>"
            )
            await telegram.send_message(message)
            logger.warning(f"Enviadas {len(alerts)} alertas de rendimiento")

    except Exception as e:
        logger.error(f"Error verificando rendimiento: {e}")


async def create_notion_metrics_entry():
    """
    Crea una entrada en Notion con las métricas del día.

    Este job corre una vez al día para crear un registro
    histórico de métricas.
    """
    try:
        from app.services.notion import get_notion_service

        collector = get_metrics_collector()
        notion = get_notion_service()

        summary = collector.get_summary()

        # Crear entrada en la base de conocimiento
        # Usamos Knowledge DB para almacenar métricas
        content = f"""# Métricas del Sistema - {datetime.now().strftime('%Y-%m-%d')}

## Resumen

- **Uptime:** {summary['uptime_human']}
- **Endpoints llamados:** {summary['endpoints']['total_calls']}
- **Agentes ejecutados:** {summary['agents']['total_calls']}
- **Tasa de éxito agentes:** {summary['agents']['success_rate']}%

## Endpoints más lentos

"""
        for ep in summary["endpoints"]["slowest"]:
            content += f"- {ep['path']}: {ep['avg_time_ms']:.0f}ms promedio\n"

        content += "\n## Agentes más lentos\n\n"
        for agent in summary["agents"]["slowest"]:
            content += f"- {agent['agent_name']}: {agent['avg_time_ms']:.0f}ms promedio\n"

        # Guardar en Knowledge DB
        await notion.create_knowledge_entry(
            title=f"Métricas {datetime.now().strftime('%Y-%m-%d')}",
            content=content,
            tags=["métricas", "sistema", "automatizado"],
        )

        logger.info("Métricas guardadas en Notion")

    except Exception as e:
        logger.error(f"Error guardando métricas en Notion: {e}")
