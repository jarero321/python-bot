"""Sistema de métricas y profiling para Carlos Command."""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ==================== DATA CLASSES ====================

@dataclass
class MetricPoint:
    """Punto de métrica individual."""

    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class EndpointMetrics:
    """Métricas de un endpoint."""

    path: str
    method: str
    call_count: int = 0
    total_time_ms: float = 0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0
    error_count: int = 0
    last_call: datetime | None = None
    recent_times: list[float] = field(default_factory=list)

    @property
    def avg_time_ms(self) -> float:
        if self.call_count == 0:
            return 0
        return self.total_time_ms / self.call_count

    @property
    def p95_time_ms(self) -> float:
        if not self.recent_times:
            return 0
        sorted_times = sorted(self.recent_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def record(self, time_ms: float, is_error: bool = False) -> None:
        """Registra una llamada."""
        self.call_count += 1
        self.total_time_ms += time_ms
        self.min_time_ms = min(self.min_time_ms, time_ms)
        self.max_time_ms = max(self.max_time_ms, time_ms)
        self.last_call = datetime.now()

        if is_error:
            self.error_count += 1

        # Mantener últimas 100 llamadas para percentiles
        self.recent_times.append(time_ms)
        if len(self.recent_times) > 100:
            self.recent_times.pop(0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "method": self.method,
            "call_count": self.call_count,
            "avg_time_ms": round(self.avg_time_ms, 2),
            "min_time_ms": round(self.min_time_ms, 2) if self.min_time_ms != float("inf") else 0,
            "max_time_ms": round(self.max_time_ms, 2),
            "p95_time_ms": round(self.p95_time_ms, 2),
            "error_count": self.error_count,
            "error_rate": round(self.error_count / self.call_count * 100, 2) if self.call_count > 0 else 0,
            "last_call": self.last_call.isoformat() if self.last_call else None,
        }


@dataclass
class AgentMetrics:
    """Métricas de un agente DSPy."""

    agent_name: str
    call_count: int = 0
    success_count: int = 0
    total_time_ms: float = 0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0
    token_count: int = 0
    recent_times: list[float] = field(default_factory=list)
    error_types: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def avg_time_ms(self) -> float:
        if self.call_count == 0:
            return 0
        return self.total_time_ms / self.call_count

    @property
    def success_rate(self) -> float:
        if self.call_count == 0:
            return 0
        return self.success_count / self.call_count * 100

    @property
    def p95_time_ms(self) -> float:
        if not self.recent_times:
            return 0
        sorted_times = sorted(self.recent_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def record(
        self,
        time_ms: float,
        success: bool,
        tokens: int = 0,
        error_type: str | None = None,
    ) -> None:
        """Registra una ejecución del agente."""
        self.call_count += 1
        self.total_time_ms += time_ms
        self.min_time_ms = min(self.min_time_ms, time_ms)
        self.max_time_ms = max(self.max_time_ms, time_ms)
        self.token_count += tokens

        if success:
            self.success_count += 1
        elif error_type:
            self.error_types[error_type] += 1

        self.recent_times.append(time_ms)
        if len(self.recent_times) > 100:
            self.recent_times.pop(0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 2),
            "avg_time_ms": round(self.avg_time_ms, 2),
            "min_time_ms": round(self.min_time_ms, 2) if self.min_time_ms != float("inf") else 0,
            "max_time_ms": round(self.max_time_ms, 2),
            "p95_time_ms": round(self.p95_time_ms, 2),
            "total_tokens": self.token_count,
            "error_types": dict(self.error_types),
        }


# ==================== METRICS COLLECTOR ====================

class MetricsCollector:
    """Colector centralizado de métricas."""

    def __init__(self):
        self._endpoints: dict[str, EndpointMetrics] = {}
        self._agents: dict[str, AgentMetrics] = {}
        self._custom_metrics: dict[str, list[MetricPoint]] = defaultdict(list)
        self._start_time = datetime.now()
        self._lock = asyncio.Lock()

    def _get_endpoint_key(self, path: str, method: str) -> str:
        return f"{method}:{path}"

    async def record_endpoint(
        self,
        path: str,
        method: str,
        time_ms: float,
        is_error: bool = False,
    ) -> None:
        """Registra métricas de un endpoint."""
        key = self._get_endpoint_key(path, method)

        async with self._lock:
            if key not in self._endpoints:
                self._endpoints[key] = EndpointMetrics(path=path, method=method)
            self._endpoints[key].record(time_ms, is_error)

    async def record_agent(
        self,
        agent_name: str,
        time_ms: float,
        success: bool,
        tokens: int = 0,
        error_type: str | None = None,
    ) -> None:
        """Registra métricas de un agente."""
        async with self._lock:
            if agent_name not in self._agents:
                self._agents[agent_name] = AgentMetrics(agent_name=agent_name)
            self._agents[agent_name].record(time_ms, success, tokens, error_type)

    async def record_custom(
        self,
        metric_name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Registra una métrica personalizada."""
        point = MetricPoint(value=value, labels=labels or {})
        async with self._lock:
            self._custom_metrics[metric_name].append(point)
            # Mantener últimas 1000 métricas
            if len(self._custom_metrics[metric_name]) > 1000:
                self._custom_metrics[metric_name].pop(0)

    def get_endpoint_metrics(self, path: str | None = None) -> list[dict]:
        """Obtiene métricas de endpoints."""
        if path:
            key = next(
                (k for k in self._endpoints if path in k),
                None,
            )
            if key:
                return [self._endpoints[key].to_dict()]
            return []

        return [m.to_dict() for m in self._endpoints.values()]

    def get_agent_metrics(self, agent_name: str | None = None) -> list[dict]:
        """Obtiene métricas de agentes."""
        if agent_name:
            if agent_name in self._agents:
                return [self._agents[agent_name].to_dict()]
            return []

        return [m.to_dict() for m in self._agents.values()]

    def get_slowest_endpoints(self, limit: int = 5) -> list[dict]:
        """Obtiene los endpoints más lentos."""
        sorted_endpoints = sorted(
            self._endpoints.values(),
            key=lambda x: x.avg_time_ms,
            reverse=True,
        )
        return [e.to_dict() for e in sorted_endpoints[:limit]]

    def get_slowest_agents(self, limit: int = 5) -> list[dict]:
        """Obtiene los agentes más lentos."""
        sorted_agents = sorted(
            self._agents.values(),
            key=lambda x: x.avg_time_ms,
            reverse=True,
        )
        return [a.to_dict() for a in sorted_agents[:limit]]

    def get_summary(self) -> dict[str, Any]:
        """Obtiene resumen de todas las métricas."""
        uptime = datetime.now() - self._start_time

        total_endpoint_calls = sum(e.call_count for e in self._endpoints.values())
        total_agent_calls = sum(a.call_count for a in self._agents.values())
        total_agent_success = sum(a.success_count for a in self._agents.values())

        return {
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_human": str(uptime).split(".")[0],
            "endpoints": {
                "total_calls": total_endpoint_calls,
                "unique_endpoints": len(self._endpoints),
                "slowest": self.get_slowest_endpoints(3),
            },
            "agents": {
                "total_calls": total_agent_calls,
                "success_rate": round(total_agent_success / total_agent_calls * 100, 2) if total_agent_calls > 0 else 0,
                "unique_agents": len(self._agents),
                "slowest": self.get_slowest_agents(3),
            },
            "custom_metrics_count": sum(len(v) for v in self._custom_metrics.values()),
        }

    def reset(self) -> None:
        """Reinicia todas las métricas."""
        self._endpoints.clear()
        self._agents.clear()
        self._custom_metrics.clear()
        self._start_time = datetime.now()


# ==================== SINGLETON ====================

_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Obtiene el colector de métricas singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# ==================== DECORATORS ====================

def profile_endpoint(func: Callable) -> Callable:
    """Decorador para medir tiempo de ejecución de endpoints."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        is_error = False

        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            is_error = True
            raise
        finally:
            elapsed_ms = (time.time() - start_time) * 1000

            # Intentar extraer path del primer argumento (Request)
            path = "unknown"
            method = "unknown"
            if args and hasattr(args[0], "url"):
                path = str(args[0].url.path)
                method = args[0].method

            collector = get_metrics_collector()
            await collector.record_endpoint(path, method, elapsed_ms, is_error)

    return wrapper


def profile_agent(agent_name: str) -> Callable:
    """Decorador para medir tiempo de ejecución de agentes."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_type = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                elapsed_ms = (time.time() - start_time) * 1000

                collector = get_metrics_collector()
                await collector.record_agent(
                    agent_name,
                    elapsed_ms,
                    success,
                    error_type=error_type,
                )

        return wrapper

    return decorator


# ==================== MIDDLEWARE ====================

async def metrics_middleware(request, call_next):
    """Middleware para registrar métricas de todas las requests."""
    start_time = time.time()
    is_error = False

    try:
        response = await call_next(request)
        is_error = response.status_code >= 400
        return response
    except Exception:
        is_error = True
        raise
    finally:
        elapsed_ms = (time.time() - start_time) * 1000
        path = request.url.path
        method = request.method

        collector = get_metrics_collector()
        await collector.record_endpoint(path, method, elapsed_ms, is_error)
