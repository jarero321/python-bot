#!/usr/bin/env python3
"""Script para probar los AI Agents de DSPy."""

import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_inbox_processor():
    """Prueba el InboxProcessorAgent."""
    from app.agents.inbox_processor import InboxProcessorAgent, MessageCategory

    print("\n" + "=" * 60)
    print("         TEST: InboxProcessorAgent")
    print("=" * 60)

    agent = InboxProcessorAgent()

    # Casos de prueba
    test_cases = [
        {
            "input": "agregar endpoint de validación para PayCash",
            "expected_category": MessageCategory.TASK,
            "description": "Tarea técnica clara",
        },
        {
            "input": "compré unos audífonos en 2500 pesos",
            "expected_category": MessageCategory.FINANCE,
            "description": "Gasto registrado",
        },
        {
            "input": "hoy entrené push, hice 3x8 en banca con 65kg",
            "expected_category": MessageCategory.GYM,
            "description": "Reporte de entrenamiento",
        },
        {
            "input": "desayuné huevos con pan, almorcé pollo con arroz",
            "expected_category": MessageCategory.NUTRITION,
            "description": "Reporte de nutrición",
        },
        {
            "input": "aprendí sobre decoradores en Python hoy",
            "expected_category": MessageCategory.KNOWLEDGE,
            "description": "Conocimiento adquirido",
        },
        {
            "input": "hola, buenos días",
            "expected_category": MessageCategory.UNKNOWN,
            "description": "Saludo sin contexto",
        },
    ]

    results = []
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['description']}")
        print(f"   Input: \"{test['input']}\"")

        try:
            result = await agent.classify_message(test["input"])
            print(f"   Categoría: {result.category.value}")
            print(f"   Confianza: {result.confidence:.0%}")
            print(f"   Título sugerido: {result.suggested_title}")

            if result.needs_clarification:
                print(f"   ⚠ Necesita clarificación: {result.clarification_question}")

            # Validar resultado
            if result.category == test["expected_category"]:
                print("   ✓ Categoría correcta")
                results.append(True)
            else:
                print(f"   ✗ Esperado: {test['expected_category'].value}")
                results.append(False)

        except Exception as e:
            print(f"   ✗ Error: {e}")
            results.append(False)

    # Resumen
    success = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"Resultados: {success}/{total} tests pasados")
    return success == total


async def test_spending_analyzer():
    """Prueba el SpendingAnalyzerAgent."""
    from app.agents.spending_analyzer import SpendingAnalyzerAgent

    print("\n" + "=" * 60)
    print("         TEST: SpendingAnalyzerAgent")
    print("=" * 60)

    agent = SpendingAnalyzerAgent()

    # Datos de contexto financiero (simulados)
    financial_context = {
        "available_budget": 5000,
        "days_until_payday": 10,
        "total_debt": 330000,
        "monthly_debt_interest": 6500,
    }

    # Casos de prueba
    test_cases = [
        {
            "description": "2500 pesos en audífonos",
            "amount": 2500,
            "expected_essential": False,
        },
        {
            "description": "despensa del super 1500 pesos",
            "amount": 1500,
            "expected_essential": True,
        },
        {
            "description": "gasolina 800 pesos",
            "amount": 800,
            "expected_essential": True,
        },
        {
            "description": "videojuego nuevo en 1200",
            "amount": 1200,
            "expected_essential": False,
        },
    ]

    results = []
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. \"{test['description']}\"")
        print(f"   Monto detectado esperado: ${test['amount']}")

        try:
            result = await agent.analyze_purchase(
                description=test["description"],
                financial_context=financial_context,
            )

            print(f"   Monto extraído: ${result.get('amount', 0)}")
            print(f"   Es esencial: {result.get('is_essential', '?')}")
            print(f"   Categoría: {result.get('category', '?')}")
            print(f"   Impacto: {result.get('budget_impact', '?')}")
            print(f"   Recomendación: {result.get('recommendation', '?')}")

            if result.get("honest_questions"):
                print("   Preguntas honestas:")
                for q in result["honest_questions"][:2]:
                    print(f"      • {q}")

            # Validación básica
            amount_ok = result.get("amount", 0) == test["amount"]
            essential_ok = result.get("is_essential") == test["expected_essential"]

            if amount_ok and essential_ok:
                print("   ✓ Análisis correcto")
                results.append(True)
            else:
                if not amount_ok:
                    print(f"   ✗ Monto incorrecto")
                if not essential_ok:
                    print(f"   ✗ Esencial incorrecto (esperado: {test['expected_essential']})")
                results.append(False)

        except Exception as e:
            print(f"   ✗ Error: {e}")
            results.append(False)

    # Resumen
    success = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"Resultados: {success}/{total} tests pasados")
    return success == total


async def test_base_agents():
    """Prueba los agents base de DSPy."""
    from app.agents.base import (
        MessageClassifier,
        TaskExtractor,
        get_dspy_lm,
    )

    print("\n" + "=" * 60)
    print("         TEST: Base DSPy Agents")
    print("=" * 60)

    # Verificar conexión con LLM
    print("\n1. Verificando conexión con LLM...")
    try:
        lm = get_dspy_lm()
        print(f"   ✓ LLM configurado: {type(lm).__name__}")
    except Exception as e:
        print(f"   ✗ Error configurando LLM: {e}")
        return False

    # Test MessageClassifier
    print("\n2. Probando MessageClassifier...")
    try:
        classifier = MessageClassifier()
        result = classifier(
            message="necesito agregar un endpoint para validar pagos",
            context="Trabajando en proyecto PayCash",
        )
        print(f"   Tipo: {result.message_type}")
        print(f"   Confianza: {result.confidence}")
        print(f"   ✓ MessageClassifier funciona")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test TaskExtractor
    print("\n3. Probando TaskExtractor...")
    try:
        extractor = TaskExtractor()
        result = extractor(
            message="agregar validación de tarjeta de crédito al checkout",
            message_type="task",
        )
        print(f"   Título: {result.task_title}")
        print(f"   Complejidad: {result.complexity}")
        print(f"   Proyecto sugerido: {result.suggested_project}")
        print(f"   ✓ TaskExtractor funciona")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print(f"\n{'=' * 40}")
    print("✓ Todos los agents base funcionan correctamente")
    return True


async def main():
    """Ejecuta todos los tests de agents."""
    print("=" * 60)
    print("         CARLOS COMMAND - AI AGENTS TEST")
    print("=" * 60)
    print()
    print("Este script prueba los AI agents de DSPy.")
    print("Asegúrate de tener GEMINI_API_KEY configurada en .env")
    print()

    # Verificar configuración
    try:
        from app.config import get_settings

        settings = get_settings()
        if not settings.gemini_api_key:
            print("✗ Error: GEMINI_API_KEY no está configurada")
            print("  Agrega GEMINI_API_KEY=tu_api_key en el archivo .env")
            return
        print(f"✓ API Key configurada (termina en ...{settings.gemini_api_key[-4:]})")
    except Exception as e:
        print(f"✗ Error cargando configuración: {e}")
        return

    # Ejecutar tests
    results = []

    # Test 1: Base agents
    print("\n" + "-" * 60)
    try:
        results.append(("Base Agents", await test_base_agents()))
    except Exception as e:
        print(f"✗ Error crítico en Base Agents: {e}")
        results.append(("Base Agents", False))

    # Test 2: Inbox Processor
    print("\n" + "-" * 60)
    try:
        results.append(("Inbox Processor", await test_inbox_processor()))
    except Exception as e:
        print(f"✗ Error crítico en Inbox Processor: {e}")
        results.append(("Inbox Processor", False))

    # Test 3: Spending Analyzer
    print("\n" + "-" * 60)
    try:
        results.append(("Spending Analyzer", await test_spending_analyzer()))
    except Exception as e:
        print(f"✗ Error crítico en Spending Analyzer: {e}")
        results.append(("Spending Analyzer", False))

    # Resumen final
    print("\n" + "=" * 60)
    print("                    RESUMEN FINAL")
    print("=" * 60)
    for name, passed in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")

    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("✓ Todos los tests pasaron correctamente")
    else:
        print("⚠ Algunos tests fallaron - revisa los detalles arriba")

    print("\n=== Test completado ===")


if __name__ == "__main__":
    asyncio.run(main())
