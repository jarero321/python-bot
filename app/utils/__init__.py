"""Utilidades de Carlos Command."""

from app.utils.errors import (
    CarlosCommandError,
    NotionAPIError,
    TelegramAPIError,
    GeminiAPIError,
    AgentError,
    ValidationError,
    ErrorCategory,
    ErrorContext,
    log_error,
    with_error_handling,
    retry_notion,
    retry_telegram,
    retry_gemini,
    safe_execute,
)

from app.utils.cache import (
    InMemoryCache,
    CacheEntry,
    get_cache,
    cached,
    NotionCacheKeys,
)

from app.utils.mappers import (
    # Priority
    parse_priority,
    priority_to_display,
    priority_to_emoji,
    PRIORITY_STR_TO_ENUM,
    PRIORITY_DISPLAY,
    PRIORITY_TO_NOTION,
    # Energy
    parse_energy,
    energy_to_display,
    ENERGY_STR_TO_ENUM,
    ENERGY_DISPLAY,
    # Complexity
    parse_complexity,
    complexity_to_display,
    downgrade_complexity,
    COMPLEXITY_STR_TO_ENUM,
    COMPLEXITY_DISPLAY,
    # Time Block
    parse_time_block,
    time_block_to_display,
    suggest_time_block_from_energy,
    TIME_BLOCK_STR_TO_ENUM,
    TIME_BLOCK_DISPLAY,
    # Status
    parse_status,
    status_to_display,
    STATUS_STR_TO_ENUM,
    STATUS_DISPLAY,
)

from app.utils.text import (
    truncate_text,
    truncate_title,
    format_duration,
    format_hours,
    clean_task_title,
    escape_html,
    make_bullet_list,
)

__all__ = [
    # Errors
    "CarlosCommandError",
    "NotionAPIError",
    "TelegramAPIError",
    "GeminiAPIError",
    "AgentError",
    "ValidationError",
    "ErrorCategory",
    "ErrorContext",
    "log_error",
    "with_error_handling",
    "retry_notion",
    "retry_telegram",
    "retry_gemini",
    "safe_execute",
    # Cache
    "InMemoryCache",
    "CacheEntry",
    "get_cache",
    "cached",
    "NotionCacheKeys",
    # Mappers
    "parse_priority",
    "priority_to_display",
    "priority_to_emoji",
    "PRIORITY_STR_TO_ENUM",
    "PRIORITY_DISPLAY",
    "PRIORITY_TO_NOTION",
    "parse_energy",
    "energy_to_display",
    "ENERGY_STR_TO_ENUM",
    "ENERGY_DISPLAY",
    "parse_complexity",
    "complexity_to_display",
    "downgrade_complexity",
    "COMPLEXITY_STR_TO_ENUM",
    "COMPLEXITY_DISPLAY",
    "parse_time_block",
    "time_block_to_display",
    "suggest_time_block_from_energy",
    "TIME_BLOCK_STR_TO_ENUM",
    "TIME_BLOCK_DISPLAY",
    "parse_status",
    "status_to_display",
    "STATUS_STR_TO_ENUM",
    "STATUS_DISPLAY",
    # Text utilities
    "truncate_text",
    "truncate_title",
    "format_duration",
    "format_hours",
    "clean_task_title",
    "escape_html",
    "make_bullet_list",
]
