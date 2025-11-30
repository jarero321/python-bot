"""
LLMProvider - Proveedor centralizado de modelos LLM.

Soporta múltiples modelos con selección automática según la tarea:
- FLASH: Tareas rápidas (clasificación, parsing, respuestas simples)
- PRO: Tareas complejas (razonamiento, análisis, planificación)
"""

import logging
from enum import Enum
from typing import Any

import dspy
import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """Tipos de modelo disponibles."""

    FLASH = "flash"  # Rápido, económico - para tareas simples
    PRO = "pro"  # Potente - para razonamiento complejo


class ModelConfig:
    """Configuración de un modelo específico."""

    def __init__(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        description: str = "",
    ):
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.description = description


# Configuraciones de modelos
MODEL_CONFIGS = {
    ModelType.FLASH: ModelConfig(
        model_id="gemini/gemini-2.0-flash-exp",
        temperature=0.7,
        max_tokens=1024,
        description="Modelo rápido para clasificación y tareas simples",
    ),
    ModelType.PRO: ModelConfig(
        model_id="gemini/gemini-2.0-flash-thinking-exp-01-21",
        temperature=0.8,
        max_tokens=4096,
        description="Modelo potente para razonamiento y análisis",
    ),
}

# Mapeo de tareas a tipo de modelo recomendado
TASK_MODEL_MAP = {
    # Tareas simples -> FLASH
    "intent_classification": ModelType.FLASH,
    "greeting": ModelType.FLASH,
    "help": ModelType.FLASH,
    "entity_extraction": ModelType.FLASH,
    "simple_query": ModelType.FLASH,
    "task_parsing": ModelType.FLASH,
    "complexity_analysis": ModelType.FLASH,
    # Tareas complejas -> PRO
    "morning_planning": ModelType.PRO,
    "debt_strategy": ModelType.PRO,
    "spending_analysis": ModelType.PRO,
    "nutrition_analysis": ModelType.PRO,
    "study_planning": ModelType.PRO,
    "task_enrichment": ModelType.PRO,
    "code_generation": ModelType.PRO,
    "multi_step_reasoning": ModelType.PRO,
}


class LLMProvider:
    """
    Proveedor centralizado de LLM.

    Gestiona la configuración de DSPy y proporciona acceso a diferentes
    modelos según la complejidad de la tarea.

    Uso:
        provider = get_llm_provider()
        provider.configure()  # Solo una vez al inicio

        # Para tareas simples (usa Flash por defecto)
        result = my_dspy_module(input)

        # Para tareas que requieren más potencia
        with provider.use_model(ModelType.PRO):
            result = complex_dspy_module(input)

        # O especificar por tipo de tarea
        with provider.for_task("morning_planning"):
            result = planner(tasks)
    """

    _instance: "LLMProvider | None" = None
    _configured: bool = False

    def __new__(cls) -> "LLMProvider":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.settings = get_settings()
        self._current_model: ModelType = ModelType.FLASH
        self._models: dict[ModelType, dspy.LM] = {}

    def configure(self, default_model: ModelType = ModelType.FLASH) -> None:
        """
        Configura el proveedor de LLM.

        Args:
            default_model: Modelo por defecto a usar
        """
        if self._configured:
            logger.debug("LLMProvider ya configurado")
            return

        logger.info("Configurando LLMProvider...")

        # Configurar API de Google
        genai.configure(api_key=self.settings.gemini_api_key)

        # Crear instancias de modelos
        for model_type, config in MODEL_CONFIGS.items():
            try:
                lm = dspy.LM(
                    model=config.model_id,
                    api_key=self.settings.gemini_api_key,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )
                self._models[model_type] = lm
                logger.info(f"Modelo {model_type.value} configurado: {config.model_id}")
            except Exception as e:
                logger.error(f"Error configurando modelo {model_type.value}: {e}")

        # Configurar DSPy con el modelo por defecto
        self._current_model = default_model
        if default_model in self._models:
            dspy.configure(lm=self._models[default_model])

        self._configured = True
        logger.info(f"LLMProvider configurado. Modelo por defecto: {default_model.value}")

    def get_model(self, model_type: ModelType) -> dspy.LM | None:
        """Obtiene una instancia de modelo específico."""
        return self._models.get(model_type)

    def set_active_model(self, model_type: ModelType) -> None:
        """Cambia el modelo activo en DSPy."""
        if model_type in self._models:
            dspy.configure(lm=self._models[model_type])
            self._current_model = model_type
            logger.debug(f"Modelo activo cambiado a: {model_type.value}")

    @property
    def current_model(self) -> ModelType:
        """Retorna el tipo de modelo actualmente activo."""
        return self._current_model

    @property
    def is_configured(self) -> bool:
        """Indica si el provider está configurado."""
        return self._configured

    def use_model(self, model_type: ModelType) -> "ModelContext":
        """
        Context manager para usar temporalmente un modelo específico.

        Uso:
            with provider.use_model(ModelType.PRO):
                result = complex_reasoning_module(input)
        """
        return ModelContext(self, model_type)

    def for_task(self, task_name: str) -> "ModelContext":
        """
        Context manager que selecciona el modelo óptimo para una tarea.

        Uso:
            with provider.for_task("morning_planning"):
                result = planner(tasks)
        """
        model_type = TASK_MODEL_MAP.get(task_name, ModelType.FLASH)
        return ModelContext(self, model_type)

    def get_recommended_model(self, task_name: str) -> ModelType:
        """Obtiene el modelo recomendado para una tarea."""
        return TASK_MODEL_MAP.get(task_name, ModelType.FLASH)

    def ensure_configured(self) -> None:
        """Asegura que el provider esté configurado."""
        if not self._configured:
            self.configure()


class ModelContext:
    """Context manager para cambio temporal de modelo."""

    def __init__(self, provider: LLMProvider, model_type: ModelType):
        self.provider = provider
        self.target_model = model_type
        self.previous_model: ModelType | None = None

    def __enter__(self) -> "ModelContext":
        self.previous_model = self.provider.current_model
        if self.target_model != self.previous_model:
            self.provider.set_active_model(self.target_model)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.previous_model and self.previous_model != self.target_model:
            self.provider.set_active_model(self.previous_model)


# Singleton accessor
_llm_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Obtiene la instancia del LLMProvider."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = LLMProvider()
    return _llm_provider


def ensure_llm_configured() -> None:
    """
    Asegura que el LLM esté configurado.

    Función de conveniencia para reemplazar setup_dspy() en los agentes.
    """
    provider = get_llm_provider()
    provider.ensure_configured()
