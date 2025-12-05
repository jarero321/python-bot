"""LLM Provider - Gestión centralizada de modelos de lenguaje."""

from app.core.llm.provider import (
    LLMProvider,
    ModelType,
    ModelConfig,
    ModelContext,
    get_llm_provider,
    ensure_llm_configured,
    TASK_MODEL_MAP,
)

from app.core.llm.prompts import (
    SYSTEM_PROMPTS,
    PROMPT_TEMPLATES,
    FEW_SHOT_EXAMPLES,
    get_system_prompt,
    get_prompt_template,
    format_prompt,
    get_few_shot_examples,
    OptimizedPromptConfig,
)

__all__ = [
    # Provider
    "LLMProvider",
    "ModelType",
    "ModelConfig",
    "ModelContext",
    "get_llm_provider",
    "ensure_llm_configured",
    "TASK_MODEL_MAP",
    # Prompts
    "SYSTEM_PROMPTS",
    "PROMPT_TEMPLATES",
    "FEW_SHOT_EXAMPLES",
    "get_system_prompt",
    "get_prompt_template",
    "format_prompt",
    "get_few_shot_examples",
    "OptimizedPromptConfig",
]
