"""Repository para manejo de métricas de agents."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentMetric

logger = logging.getLogger(__name__)


class MetricsRepository:
    """Repository para operaciones CRUD de AgentMetric."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_execution(
        self,
        agent_name: str,
        execution_time_ms: int,
        success: bool = True,
        tokens_used: int | None = None,
        input_length: int | None = None,
        output_length: int | None = None,
        confidence_score: float | None = None,
        context: dict[str, Any] | None = None,
        error_message: str | None = None,
        session_id: str | None = None,
    ) -> AgentMetric:
        """Registra una ejecución de un agent."""
        metric = AgentMetric(
            agent_name=agent_name,
            session_id=session_id,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            success=success,
            input_length=input_length,
            output_length=output_length,
            confidence_score=confidence_score,
            context=json.dumps(context) if context else None,
            error_message=error_message,
        )
        self.session.add(metric)
        await self.session.flush()

        if not success:
            logger.warning(f"Agent {agent_name} falló: {error_message}")
        else:
            logger.debug(f"Métrica registrada: {agent_name} en {execution_time_ms}ms")

        return metric

    async def log_user_feedback(
        self, metric_id: int, feedback: str
    ) -> AgentMetric | None:
        """Registra feedback del usuario para una métrica."""
        result = await self.session.execute(
            select(AgentMetric).where(AgentMetric.id == metric_id)
        )
        metric = result.scalar_one_or_none()
        if metric:
            metric.user_feedback = feedback
            await self.session.flush()
            logger.info(f"Feedback '{feedback}' registrado para métrica {metric_id}")
        return metric

    async def get_agent_stats(
        self, agent_name: str, days: int = 7
    ) -> dict[str, Any]:
        """Obtiene estadísticas de un agent en los últimos N días."""
        since = datetime.utcnow() - timedelta(days=days)

        # Total de ejecuciones
        total_result = await self.session.execute(
            select(func.count(AgentMetric.id)).where(
                AgentMetric.agent_name == agent_name,
                AgentMetric.created_at >= since,
            )
        )
        total = total_result.scalar() or 0

        # Ejecuciones exitosas
        success_result = await self.session.execute(
            select(func.count(AgentMetric.id)).where(
                AgentMetric.agent_name == agent_name,
                AgentMetric.created_at >= since,
                AgentMetric.success == True,  # noqa: E712
            )
        )
        successful = success_result.scalar() or 0

        # Tiempo promedio
        avg_time_result = await self.session.execute(
            select(func.avg(AgentMetric.execution_time_ms)).where(
                AgentMetric.agent_name == agent_name,
                AgentMetric.created_at >= since,
                AgentMetric.success == True,  # noqa: E712
            )
        )
        avg_time = avg_time_result.scalar() or 0

        # Confianza promedio
        avg_confidence_result = await self.session.execute(
            select(func.avg(AgentMetric.confidence_score)).where(
                AgentMetric.agent_name == agent_name,
                AgentMetric.created_at >= since,
                AgentMetric.confidence_score.isnot(None),
            )
        )
        avg_confidence = avg_confidence_result.scalar()

        # Tokens totales
        tokens_result = await self.session.execute(
            select(func.sum(AgentMetric.tokens_used)).where(
                AgentMetric.agent_name == agent_name,
                AgentMetric.created_at >= since,
            )
        )
        total_tokens = tokens_result.scalar() or 0

        return {
            "agent_name": agent_name,
            "period_days": days,
            "total_executions": total,
            "successful_executions": successful,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "avg_execution_time_ms": round(avg_time, 2),
            "avg_confidence_score": round(avg_confidence, 3) if avg_confidence else None,
            "total_tokens_used": total_tokens,
        }

    async def get_all_agents_summary(self, days: int = 7) -> list[dict[str, Any]]:
        """Obtiene un resumen de todos los agents."""
        since = datetime.utcnow() - timedelta(days=days)

        # Obtener nombres de agents únicos
        agents_result = await self.session.execute(
            select(AgentMetric.agent_name)
            .distinct()
            .where(AgentMetric.created_at >= since)
        )
        agent_names = [row[0] for row in agents_result.fetchall()]

        summaries = []
        for agent_name in agent_names:
            stats = await self.get_agent_stats(agent_name, days)
            summaries.append(stats)

        return sorted(summaries, key=lambda x: x["total_executions"], reverse=True)

    async def get_recent_errors(
        self, agent_name: str | None = None, limit: int = 10
    ) -> list[AgentMetric]:
        """Obtiene los errores más recientes."""
        query = select(AgentMetric).where(AgentMetric.success == False)  # noqa: E712

        if agent_name:
            query = query.where(AgentMetric.agent_name == agent_name)

        query = query.order_by(AgentMetric.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())
