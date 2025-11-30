"""
Domain Services - Servicios de dominio que combinan repositorios y RAG.

Estos servicios encapsulan lógica de negocio compleja que involucra
múltiples repositorios o componentes como el RAG.
"""

from app.domain.services.task_service import TaskService, get_task_service
from app.domain.services.project_service import ProjectService, get_project_service

__all__ = [
    "TaskService",
    "get_task_service",
    "ProjectService",
    "get_project_service",
]
