"""
NotionProjectRepository - Implementación del repositorio de proyectos usando Notion.
"""

import logging
from datetime import date, datetime
from typing import Any

from app.domain.entities.project import (
    Project,
    ProjectFilter,
    ProjectType,
    ProjectStatus,
)
from app.domain.repositories.base import IProjectRepository
from app.services.notion import (
    get_notion_service,
    NotionService,
    ProjectTipo,
    ProjectEstado,
)

logger = logging.getLogger(__name__)


class NotionProjectRepository(IProjectRepository):
    """
    Repositorio de proyectos usando Notion como backend.
    """

    def __init__(self, notion_service: NotionService | None = None):
        self._notion = notion_service or get_notion_service()

    # ==================== Mappers ====================

    def _map_type_to_notion(self, project_type: ProjectType) -> ProjectTipo:
        """Mapea tipo del dominio a Notion."""
        mapping = {
            ProjectType.WORK: ProjectTipo.TRABAJO,
            ProjectType.FREELANCE: ProjectTipo.FREELANCE,
            ProjectType.LEARNING: ProjectTipo.APRENDIZAJE,
            ProjectType.SIDE_PROJECT: ProjectTipo.SIDE_PROJECT,
            ProjectType.PERSONAL: ProjectTipo.PERSONAL,
            ProjectType.HOBBY: ProjectTipo.HOBBY,
            ProjectType.FINANCIAL: ProjectTipo.FINANCIERO,
            ProjectType.SEARCH: ProjectTipo.BUSQUEDA,
        }
        return mapping.get(project_type, ProjectTipo.PERSONAL)

    def _map_type_from_notion(self, notion_type: str) -> ProjectType:
        """Mapea tipo de Notion a dominio."""
        mapping = {
            "💼 Trabajo": ProjectType.WORK,
            "💰 Freelance": ProjectType.FREELANCE,
            "📚 Aprendizaje": ProjectType.LEARNING,
            "🚀 Side Project": ProjectType.SIDE_PROJECT,
            "🏠 Personal": ProjectType.PERSONAL,
            "🎯 Hobby": ProjectType.HOBBY,
            "💳 Financiero": ProjectType.FINANCIAL,
            "🔍 Búsqueda": ProjectType.SEARCH,
        }
        return mapping.get(notion_type, ProjectType.PERSONAL)

    def _map_status_to_notion(self, status: ProjectStatus) -> ProjectEstado:
        """Mapea estado del dominio a Notion."""
        mapping = {
            ProjectStatus.IDEA: ProjectEstado.IDEA,
            ProjectStatus.PLANNING: ProjectEstado.PLANNING,
            ProjectStatus.ACTIVE: ProjectEstado.ACTIVO,
            ProjectStatus.WAITING: ProjectEstado.ESPERANDO,
            ProjectStatus.PAUSED: ProjectEstado.PAUSADO,
            ProjectStatus.COMPLETED: ProjectEstado.COMPLETADO,
            ProjectStatus.CANCELLED: ProjectEstado.CANCELADO,
        }
        return mapping.get(status, ProjectEstado.IDEA)

    def _map_status_from_notion(self, notion_status: str) -> ProjectStatus:
        """Mapea estado de Notion a dominio."""
        mapping = {
            "💡 Idea": ProjectStatus.IDEA,
            "📝 Planning": ProjectStatus.PLANNING,
            "🟢 Activo": ProjectStatus.ACTIVE,
            "🟡 Esperando": ProjectStatus.WAITING,
            "⏸️ Pausado": ProjectStatus.PAUSED,
            "✅ Completado": ProjectStatus.COMPLETED,
            "❌ Cancelado": ProjectStatus.CANCELLED,
        }
        return mapping.get(notion_status, ProjectStatus.IDEA)

    def _notion_to_project(self, notion_data: dict[str, Any]) -> Project:
        """Convierte datos de Notion a entidad Project."""
        props = notion_data.get("properties", {})

        # Extraer nombre
        title_prop = props.get("Proyecto", {}).get("title", [])
        name = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

        # Extraer tipo
        tipo_prop = props.get("Tipo", {}).get("select", {})
        tipo = tipo_prop.get("name", "") if tipo_prop else ""

        # Extraer estado
        estado_prop = props.get("Estado", {}).get("select", {})
        estado = estado_prop.get("name", "") if estado_prop else ""

        # Extraer progreso
        progreso = props.get("Progreso", {}).get("number", 0) or 0

        # Extraer descripción
        desc_prop = props.get("Descripción", {}).get("rich_text", [])
        description = desc_prop[0].get("text", {}).get("content", "") if desc_prop else None

        # Extraer fechas
        start_prop = props.get("Fecha Inicio", {}).get("date", {})
        start_date = None
        if start_prop and start_prop.get("start"):
            try:
                start_date = date.fromisoformat(start_prop["start"])
            except ValueError:
                pass

        target_prop = props.get("Fecha Target", {}).get("date", {})
        target_date = None
        if target_prop and target_prop.get("start"):
            try:
                target_date = date.fromisoformat(target_prop["start"])
            except ValueError:
                pass

        # Extraer área
        area_prop = props.get("Área", {}).get("select", {})
        area = area_prop.get("name", "") if area_prop else None

        # Extraer tareas relacionadas
        tareas_prop = props.get("Tareas", {}).get("relation", [])
        task_ids = [t.get("id") for t in tareas_prop] if tareas_prop else []

        return Project(
            id=notion_data.get("id", ""),
            name=name,
            type=self._map_type_from_notion(tipo),
            status=self._map_status_from_notion(estado),
            description=description,
            progress=int(progreso),
            start_date=start_date,
            target_date=target_date,
            area=area,
            task_ids=task_ids,
            total_tasks=len(task_ids),
            created_at=datetime.fromisoformat(
                notion_data.get("created_time", "").replace("Z", "+00:00")
            ) if notion_data.get("created_time") else None,
            _raw=notion_data,
        )

    def _project_to_notion_properties(self, project: Project) -> dict[str, Any]:
        """Convierte Project a properties de Notion."""
        properties: dict[str, Any] = {
            "Proyecto": {"title": [{"text": {"content": project.name}}]},
            "Tipo": {"select": {"name": self._map_type_to_notion(project.type).value}},
            "Estado": {"select": {"name": self._map_status_to_notion(project.status).value}},
        }

        if project.description:
            properties["Descripción"] = {
                "rich_text": [{"text": {"content": project.description}}]
            }

        if project.progress is not None:
            properties["Progreso"] = {"number": project.progress}

        if project.start_date:
            properties["Fecha Inicio"] = {"date": {"start": project.start_date.isoformat()}}

        if project.target_date:
            properties["Fecha Target"] = {"date": {"start": project.target_date.isoformat()}}

        return properties

    # ==================== CRUD ====================

    async def get_by_id(self, id: str) -> Project | None:
        """Obtiene un proyecto por su ID."""
        try:
            page = await self._notion.get_page(id)
            if page:
                return self._notion_to_project(page)
            return None
        except Exception as e:
            logger.error(f"Error obteniendo proyecto {id}: {e}")
            return None

    async def create(self, project: Project) -> Project:
        """Crea un nuevo proyecto."""
        result = await self._notion.create_project(
            nombre=project.name,
            tipo=self._map_type_to_notion(project.type),
            objetivo=project.description,  # NotionService usa 'objetivo' no 'descripcion'
        )

        if result:
            return self._notion_to_project(result)
        raise Exception("Error creando proyecto en Notion")

    async def update(self, project: Project) -> Project:
        """Actualiza un proyecto existente."""
        properties = self._project_to_notion_properties(project)

        try:
            result = await self._notion.client.pages.update(
                page_id=project.id,
                properties=properties,
            )
            return self._notion_to_project(result)
        except Exception as e:
            logger.error(f"Error actualizando proyecto {project.id}: {e}")
            raise

    async def delete(self, id: str) -> bool:
        """Archiva un proyecto."""
        try:
            await self._notion.client.pages.update(
                page_id=id,
                archived=True,
            )
            return True
        except Exception as e:
            logger.error(f"Error eliminando proyecto {id}: {e}")
            return False

    # ==================== Queries ====================

    async def find(self, filter: ProjectFilter) -> list[Project]:
        """Busca proyectos según filtros."""
        active_only = filter.is_active if filter.is_active is not None else False
        projects = await self._notion.get_projects(active_only=active_only)
        result = [self._notion_to_project(p) for p in projects]

        # Aplicar filtros adicionales
        if filter.type:
            types = [filter.type] if isinstance(filter.type, ProjectType) else filter.type
            result = [p for p in result if p.type in types]

        if filter.status:
            statuses = [filter.status] if isinstance(filter.status, ProjectStatus) else filter.status
            result = [p for p in result if p.status in statuses]

        if filter.search_text:
            query = filter.search_text.lower()
            result = [p for p in result if query in p.name.lower()]

        return result[:filter.limit]

    async def get_active(self) -> list[Project]:
        """Obtiene proyectos activos."""
        projects = await self._notion.get_projects(active_only=True)
        return [self._notion_to_project(p) for p in projects]

    async def get_by_status(self, status: ProjectStatus) -> list[Project]:
        """Obtiene proyectos por estado."""
        all_projects = await self.find(ProjectFilter())
        return [p for p in all_projects if p.status == status]

    async def search_by_name(self, query: str) -> list[Project]:
        """Busca proyectos por nombre."""
        return await self.find(ProjectFilter(search_text=query))

    # ==================== Updates Específicos ====================

    async def update_status(self, id: str, status: ProjectStatus) -> Project | None:
        """Actualiza el estado de un proyecto."""
        notion_status = self._map_status_to_notion(status)
        result = await self._notion.update_project_status(id, notion_status)
        if result:
            return self._notion_to_project(result)
        return None

    async def update_progress(self, id: str, progress: int) -> Project | None:
        """Actualiza el progreso de un proyecto."""
        try:
            result = await self._notion.client.pages.update(
                page_id=id,
                properties={
                    "Progreso": {"number": max(0, min(100, progress))}
                },
            )
            return self._notion_to_project(result)
        except Exception as e:
            logger.error(f"Error actualizando progreso {id}: {e}")
            return None

    async def complete(self, id: str) -> Project | None:
        """Marca un proyecto como completado."""
        return await self.update_status(id, ProjectStatus.COMPLETED)

    async def find_by_name(self, name: str) -> Project | None:
        """
        Busca un proyecto por nombre (exacto o parcial).

        Args:
            name: Nombre del proyecto a buscar

        Returns:
            Project si se encuentra, None si no existe
        """
        try:
            all_projects = await self.get_active()

            if not name:
                return None

            name_lower = name.lower().strip()

            # Búsqueda exacta primero
            for project in all_projects:
                if project.name.lower() == name_lower:
                    return project

            # Búsqueda parcial (el nombre está contenido en el proyecto)
            for project in all_projects:
                if name_lower in project.name.lower():
                    return project

            # Búsqueda inversa (el proyecto está contenido en el nombre)
            for project in all_projects:
                if project.name.lower() in name_lower:
                    return project

            return None

        except Exception as e:
            logger.error(f"Error buscando proyecto por nombre '{name}': {e}")
            return None
