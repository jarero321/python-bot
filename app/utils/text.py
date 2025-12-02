"""
Utilidades de texto - Funciones comunes para manipulación de strings.

Consolida funciones duplicadas de truncamiento y formateo.
"""


def truncate_text(text: str, max_length: int = 50, ellipsis: str = "...") -> str:
    """
    Trunca texto respetando límites de palabras.

    Args:
        text: Texto a truncar
        max_length: Longitud máxima (default 50)
        ellipsis: String a agregar si se trunca (default "...")

    Returns:
        Texto truncado si excede max_length
    """
    if not text or len(text) <= max_length:
        return text or ""

    # Intentar cortar en espacio para no cortar palabras
    cut_point = text.rfind(" ", 0, max_length - len(ellipsis))
    if cut_point == -1:
        cut_point = max_length - len(ellipsis)

    return text[:cut_point] + ellipsis


def truncate_title(title: str, max_length: int = 50) -> str:
    """Alias para truncar títulos de tareas."""
    return truncate_text(title, max_length)


def format_duration(minutes: int | None) -> str:
    """
    Formatea minutos a string legible.

    Args:
        minutes: Minutos totales

    Returns:
        String formateado como "Xh Ym" o "Xm"
    """
    if not minutes:
        return ""

    hours = minutes // 60
    mins = minutes % 60

    if hours and mins:
        return f"{hours}h {mins}m"
    elif hours:
        return f"{hours}h"
    else:
        return f"{mins}m"


def format_hours(minutes: int | None) -> str:
    """
    Formatea minutos a horas con decimal.

    Args:
        minutes: Minutos totales

    Returns:
        String como "X.Xh"
    """
    if not minutes:
        return "0h"

    hours = minutes / 60
    return f"{hours:.1f}h"


def clean_task_title(title: str) -> str:
    """
    Limpia un título de tarea removiendo prefijos comunes.

    Args:
        title: Título original

    Returns:
        Título limpio
    """
    # Remover prefijos comunes de comandos
    prefixes = [
        "crear tarea",
        "nueva tarea",
        "agregar tarea",
        "tarea:",
        "task:",
    ]

    title_lower = title.lower().strip()
    for prefix in prefixes:
        if title_lower.startswith(prefix):
            title = title[len(prefix):].strip()
            break

    return title.strip()


def escape_html(text: str) -> str:
    """Escapa caracteres especiales para HTML/Telegram."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def make_bullet_list(items: list[str], bullet: str = "•", max_items: int | None = None) -> str:
    """
    Crea lista con viñetas.

    Args:
        items: Lista de items
        bullet: Carácter de viñeta
        max_items: Máximo de items a mostrar (None = todos)

    Returns:
        String formateado como lista
    """
    if not items:
        return ""

    display_items = items[:max_items] if max_items else items
    lines = [f"{bullet} {item}" for item in display_items]

    if max_items and len(items) > max_items:
        remaining = len(items) - max_items
        lines.append(f"  ... y {remaining} más")

    return "\n".join(lines)
