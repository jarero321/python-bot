"""
DSPyParser - Utilidades centralizadas para parsear outputs de DSPy.

Reemplaza el código duplicado de _parse_list, _parse_enum, etc.
que existe en 10+ agentes.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Enum)


class DSPyParser:
    """
    Parser centralizado para outputs de DSPy.

    Métodos estáticos para uso sin instanciar:
        items = DSPyParser.parse_list(result.subtasks)
        priority = DSPyParser.parse_enum(result.priority, TaskPrioridad)
        data = DSPyParser.parse_json(result.json_output)
    """

    # ==================== LIST PARSING ====================

    @staticmethod
    def parse_list(
        value: str | list | None,
        separator: str = "|",
        strip: bool = True,
        filter_empty: bool = True,
    ) -> list[str]:
        """
        Parsea un valor a lista de strings.

        Args:
            value: Valor a parsear (string separado, lista, o None)
            separator: Separador para strings (default: "|")
            strip: Si eliminar espacios de cada elemento
            filter_empty: Si filtrar elementos vacíos

        Returns:
            Lista de strings

        Ejemplos:
            parse_list("a|b|c") -> ["a", "b", "c"]
            parse_list(["a", "b"]) -> ["a", "b"]
            parse_list(None) -> []
            parse_list("a; b; c", separator=";") -> ["a", "b", "c"]
        """
        if value is None:
            return []

        if isinstance(value, list):
            items = [str(item) for item in value]
        else:
            value_str = str(value)
            if not value_str or value_str.lower() in ("none", "n/a", "null", "[]"):
                return []
            items = value_str.split(separator)

        if strip:
            items = [item.strip() for item in items]

        if filter_empty:
            items = [item for item in items if item]

        return items

    @staticmethod
    def parse_numbered_list(value: str | None) -> list[str]:
        """
        Parsea una lista numerada a lista de strings.

        Ejemplos:
            "1. Item uno\n2. Item dos" -> ["Item uno", "Item dos"]
            "- Item a\n- Item b" -> ["Item a", "Item b"]
        """
        if not value:
            return []

        lines = str(value).strip().split("\n")
        items = []

        for line in lines:
            line = line.strip()
            # Remover numeración: "1. ", "1) ", "- ", "* "
            cleaned = re.sub(r"^(\d+[\.\)]\s*|[-*]\s*)", "", line)
            if cleaned:
                items.append(cleaned)

        return items

    # ==================== ENUM PARSING ====================

    @staticmethod
    def parse_enum(
        value: str | None,
        enum_class: Type[T],
        default: T | None = None,
        by_value: bool = True,
    ) -> T | None:
        """
        Parsea un string a un enum.

        Args:
            value: Valor a parsear
            enum_class: Clase del enum
            default: Valor por defecto si no hay match
            by_value: Si buscar por .value (True) o por .name (False)

        Returns:
            Miembro del enum o default

        Ejemplos:
            parse_enum("urgente", TaskPrioridad) -> TaskPrioridad.URGENTE
            parse_enum("URGENTE", TaskPrioridad, by_value=False) -> TaskPrioridad.URGENTE
        """
        if not value:
            return default

        value_lower = str(value).lower().strip()

        for member in enum_class:
            if by_value:
                # Comparar con .value
                member_value = str(member.value).lower()
                # Buscar match exacto o parcial
                if value_lower == member_value or value_lower in member_value:
                    return member
            else:
                # Comparar con .name
                if value_lower == member.name.lower():
                    return member

        return default

    @staticmethod
    def parse_enum_flexible(
        value: str | None,
        mapping: dict[str, T],
        default: T | None = None,
    ) -> T | None:
        """
        Parsea usando un mapeo flexible de strings a enums.

        Args:
            value: Valor a parsear
            mapping: Dict de string -> enum member
            default: Valor por defecto

        Ejemplos:
            mapping = {
                "urgente": TaskPrioridad.URGENTE,
                "urgent": TaskPrioridad.URGENTE,
                "asap": TaskPrioridad.URGENTE,
            }
            parse_enum_flexible("urgent", mapping) -> TaskPrioridad.URGENTE
        """
        if not value:
            return default

        value_lower = str(value).lower().strip()
        return mapping.get(value_lower, default)

    # ==================== JSON PARSING ====================

    @staticmethod
    def parse_json(
        value: str | dict | list | None,
        default: dict | list | None = None,
    ) -> dict | list | None:
        """
        Parsea un valor a dict o list.

        Args:
            value: JSON string, dict, o list
            default: Valor por defecto si falla

        Returns:
            Dict, list, o default
        """
        if value is None:
            return default

        if isinstance(value, (dict, list)):
            return value

        try:
            value_str = str(value).strip()

            # Manejar strings vacíos o None-like
            if not value_str or value_str.lower() in ("none", "null", "{}"):
                return default if default is not None else {}

            return json.loads(value_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Error parseando JSON: {e}")
            return default

    @staticmethod
    def parse_json_safe(value: str | None, default: dict | None = None) -> dict:
        """Versión segura que siempre retorna dict."""
        result = DSPyParser.parse_json(value, default)
        if isinstance(result, dict):
            return result
        return default or {}

    # ==================== DATE PARSING ====================

    @staticmethod
    def parse_date(
        value: str | None,
        formats: list[str] | None = None,
    ) -> str | None:
        """
        Parsea un string de fecha a formato YYYY-MM-DD.

        Args:
            value: String de fecha
            formats: Formatos a intentar (default: varios comunes)

        Returns:
            Fecha en formato YYYY-MM-DD o None
        """
        if not value or str(value).lower() in ("none", "n/a", "null", ""):
            return None

        value_str = str(value).strip()

        # Formatos a intentar
        if formats is None:
            formats = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
                "%d.%m.%Y",
            ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(value_str, fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Intentar parseo relativo
        return DSPyParser._parse_relative_date(value_str)

    @staticmethod
    def _parse_relative_date(value: str) -> str | None:
        """Parsea fechas relativas como 'mañana', 'próximo lunes', etc."""
        value_lower = value.lower().strip()
        today = datetime.now()

        relative_dates = {
            "hoy": today,
            "today": today,
            "mañana": today + timedelta(days=1),
            "tomorrow": today + timedelta(days=1),
            "pasado mañana": today + timedelta(days=2),
            "pasado": today + timedelta(days=2),
        }

        if value_lower in relative_dates:
            return relative_dates[value_lower].strftime("%Y-%m-%d")

        # "próximo lunes", "next monday", etc.
        days_es = {
            "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
            "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
        }
        days_en = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }

        for day_name, day_num in {**days_es, **days_en}.items():
            if day_name in value_lower:
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target = today + timedelta(days=days_ahead)
                return target.strftime("%Y-%m-%d")

        return None

    # ==================== NUMERIC PARSING ====================

    @staticmethod
    def parse_int(
        value: str | int | float | None,
        default: int = 0,
        min_val: int | None = None,
        max_val: int | None = None,
    ) -> int:
        """Parsea un valor a entero con límites opcionales."""
        if value is None:
            return default

        try:
            result = int(float(str(value)))

            if min_val is not None:
                result = max(result, min_val)
            if max_val is not None:
                result = min(result, max_val)

            return result
        except (ValueError, TypeError):
            return default

    @staticmethod
    def parse_float(
        value: str | int | float | None,
        default: float = 0.0,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> float:
        """Parsea un valor a float con límites opcionales."""
        if value is None:
            return default

        try:
            result = float(str(value))

            if min_val is not None:
                result = max(result, min_val)
            if max_val is not None:
                result = min(result, max_val)

            return result
        except (ValueError, TypeError):
            return default

    @staticmethod
    def parse_confidence(value: Any, default: float = 0.5) -> float:
        """Parsea un valor de confianza (0.0-1.0)."""
        return DSPyParser.parse_float(value, default, min_val=0.0, max_val=1.0)

    # ==================== BOOLEAN PARSING ====================

    @staticmethod
    def parse_bool(value: Any, default: bool = False) -> bool:
        """Parsea un valor a booleano."""
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        value_str = str(value).lower().strip()

        truthy = ("true", "yes", "si", "sí", "1", "on", "enabled")
        falsy = ("false", "no", "0", "off", "disabled", "none")

        if value_str in truthy:
            return True
        if value_str in falsy:
            return False

        return default

    # ==================== STRING PARSING ====================

    @staticmethod
    def parse_string(
        value: Any,
        default: str = "",
        max_length: int | None = None,
        strip: bool = True,
    ) -> str:
        """Parsea un valor a string limpio."""
        if value is None or str(value).lower() in ("none", "null", "n/a"):
            return default

        result = str(value)

        if strip:
            result = result.strip()

        if max_length and len(result) > max_length:
            result = result[:max_length]

        return result or default

    @staticmethod
    def clean_llm_output(value: str | None) -> str:
        """Limpia output típico de LLM (quita markdown, etc.)."""
        if not value:
            return ""

        result = str(value)

        # Remover bloques de código
        result = re.sub(r"```[\w]*\n?", "", result)

        # Remover asteriscos de bold/italic
        result = re.sub(r"\*+", "", result)

        # Normalizar espacios
        result = " ".join(result.split())

        return result.strip()

    # ==================== ENTITY EXTRACTION ====================

    @staticmethod
    def parse_entities(entities_str: str | None) -> dict[str, str]:
        """
        Parsea string de entidades en formato "key:value|key2:value2".

        Ejemplos:
            "amount:3000|item:airpods" -> {"amount": "3000", "item": "airpods"}
        """
        if not entities_str or entities_str.lower() in ("none", "vacío", "", "null"):
            return {}

        entities = {}
        try:
            pairs = entities_str.split("|")
            for pair in pairs:
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    entities[key.strip().lower()] = value.strip()
        except Exception as e:
            logger.debug(f"Error parseando entities: {e}")

        return entities

    @staticmethod
    def extract_price(text: str) -> int | None:
        """Extrae precio de un texto."""
        if not text:
            return None

        patterns = [
            r"\$\s*([\d,]+(?:\.\d{2})?)",  # $3000 o $3,000.00
            r"([\d,]+)\s*(?:pesos|mxn|usd)",  # 3000 pesos
            r"por\s*([\d,]+)",  # por 3000
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount = match.group(1).replace(",", "")
                    return int(float(amount))
                except ValueError:
                    continue

        return None
