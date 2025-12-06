"""
Carlos Brain - Sistema de IA unificado.

Un solo cerebro que:
- Entiende todos los dominios (tareas, finanzas, salud, planning)
- Mantiene contexto de conversación
- Toma decisiones inteligentes
- Se extiende agregando Tools, no código
"""

from app.brain.core import CarlosBrain, get_brain
from app.brain.memory import WorkingMemory, MemoryManager
from app.brain.tools import ToolRegistry

__all__ = [
    "CarlosBrain",
    "get_brain",
    "WorkingMemory",
    "MemoryManager",
    "ToolRegistry",
]
