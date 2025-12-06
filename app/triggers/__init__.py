"""
Triggers para Carlos Brain.

Los triggers son eventos programados que activan el Brain.
Solo disparan, NO contienen lógica de negocio - eso lo hace el Brain.
"""

from app.triggers.scheduler import setup_scheduler, shutdown_scheduler

__all__ = ["setup_scheduler", "shutdown_scheduler"]
