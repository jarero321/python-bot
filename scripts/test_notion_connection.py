#!/usr/bin/env python3
"""Script para probar la conexión con Notion y validar el schema."""

import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from app.services.notion import (
        get_notion_service,
        NotionDatabase,
        TaskEstado,
        TaskContexto,
        WorkoutTipo,
        InboxFuente,
    )

    print("=" * 60)
    print("         NOTION CONNECTION & SCHEMA TEST")
    print("=" * 60)
    print()

    notion = get_notion_service()

    # Test 1: Conexión básica
    print("1. Probando conexión...")
    if await notion.test_connection():
        print("   ✓ Conexión exitosa\n")
    else:
        print("   ✗ Error de conexión. Verifica NOTION_API_KEY\n")
        return

    # Test 2: Verificar acceso a todas las databases
    print("2. Verificando acceso a databases...")
    databases = {
        "📥 Inbox": NotionDatabase.INBOX,
        "✅ Tasks": NotionDatabase.TASKS,
        "📁 Projects": NotionDatabase.PROJECTS,
        "📚 Knowledge": NotionDatabase.KNOWLEDGE,
        "🍽️ Nutrition": NotionDatabase.NUTRITION,
        "🏋️ Workouts": NotionDatabase.WORKOUTS,
        "💰 Transactions": NotionDatabase.TRANSACTIONS,
        "💳 Debts": NotionDatabase.DEBTS,
    }

    db_status = {}
    for name, db_id in databases.items():
        try:
            response = await notion.client.databases.retrieve(database_id=db_id)
            title_list = response.get("title", [])
            title = title_list[0].get("plain_text", "Sin título") if title_list else "Sin título"
            print(f"   ✓ {name}: {title}")
            db_status[name] = True
        except Exception as e:
            print(f"   ✗ {name}: Error - {e}")
            db_status[name] = False

    print()

    # Test 3: Verificar schema de Tasks (campos críticos)
    print("3. Verificando schema de Tasks...")
    try:
        response = await notion.client.databases.retrieve(
            database_id=NotionDatabase.TASKS
        )
        props = response.get("properties", {})
        required_fields = [
            "Tarea",
            "Contexto",
            "Estado",
            "Prioridad",
            "Complejidad",
            "Energía",
            "Fecha Do",
            "Fecha Due",
            "Fecha Done",
            "Bloqueada",
            "Blocker",
            "Proyecto",
            "Notas",
        ]
        for field in required_fields:
            if field in props:
                field_type = props[field].get("type", "unknown")
                print(f"   ✓ {field}: {field_type}")
            else:
                print(f"   ✗ {field}: NO ENCONTRADO")
    except Exception as e:
        print(f"   ✗ Error verificando schema: {e}")
    print()

    # Test 4: Obtener tareas pendientes (con nombres correctos)
    print("4. Obteniendo tareas pendientes...")
    tasks = await notion.get_pending_tasks(limit=5)
    if tasks:
        print(f"   ✓ {len(tasks)} tareas encontradas:")
        for task in tasks[:5]:
            props = task.get("properties", {})
            # Campo correcto: "Tarea" (Title)
            title_prop = props.get("Tarea", {}).get("title", [])
            task_name = (
                title_prop[0].get("text", {}).get("content", "Sin título")
                if title_prop
                else "Sin título"
            )
            # Campo correcto: "Estado" (Select)
            estado_prop = props.get("Estado", {}).get("select", {})
            estado = estado_prop.get("name", "?") if estado_prop else "?"
            # Campo correcto: "Contexto" (Select)
            contexto_prop = props.get("Contexto", {}).get("select", {})
            contexto = contexto_prop.get("name", "?") if contexto_prop else "?"
            print(f"      [{estado}] {task_name} ({contexto})")
    else:
        print("   ⚠ No hay tareas pendientes (o error de acceso)")
    print()

    # Test 5: Obtener proyectos activos
    print("5. Obteniendo proyectos activos...")
    projects = await notion.get_projects(active_only=True)
    if projects:
        print(f"   ✓ {len(projects)} proyectos encontrados:")
        for project in projects[:5]:
            props = project.get("properties", {})
            # Campo correcto: "Proyecto" (Title)
            title_prop = props.get("Proyecto", {}).get("title", [])
            project_name = (
                title_prop[0].get("text", {}).get("content", "Sin título")
                if title_prop
                else "Sin título"
            )
            # Campo correcto: "Tipo" (Select)
            tipo_prop = props.get("Tipo", {}).get("select", {})
            tipo = tipo_prop.get("name", "?") if tipo_prop else "?"
            print(f"      - {project_name} ({tipo})")
    else:
        print("   ⚠ No hay proyectos activos (o error de acceso)")
    print()

    # Test 6: Obtener deudas activas
    print("6. Obteniendo deudas activas...")
    debt_summary = await notion.get_debt_summary()
    if debt_summary.get("deudas"):
        print(f"   ✓ Total deuda: ${debt_summary['total_deuda']:,.2f}")
        print(f"   ✓ Pago mínimo mensual: ${debt_summary['total_pago_minimo']:,.2f}")
        print(f"   ✓ Interés mensual: ${debt_summary['total_interes_mensual']:,.2f}")
        for debt in debt_summary["deudas"]:
            print(f"      - {debt['nombre']}: ${debt['monto']:,.2f} ({debt['tasa']}% tasa)")
    else:
        print("   ⚠ No hay deudas activas (o error de acceso)")
    print()

    # Test 7: Verificar último workout
    print("7. Buscando último workout de cada tipo...")
    for tipo in [WorkoutTipo.PUSH, WorkoutTipo.PULL, WorkoutTipo.LEGS]:
        workout = await notion.get_last_workout_by_type(tipo)
        if workout:
            props = workout.get("properties", {})
            fecha_prop = props.get("Fecha", {}).get("title", [])
            fecha = (
                fecha_prop[0].get("text", {}).get("content", "?")
                if fecha_prop
                else "?"
            )
            print(f"   ✓ {tipo.value}: {fecha}")
        else:
            print(f"   ⚠ {tipo.value}: Sin registros")
    print()

    # Test 8: Crear item de prueba en Inbox
    print("8. Test de creación en Inbox")
    response = input("   ¿Crear item de prueba en Inbox? (s/n): ").strip().lower()
    if response == "s":
        result = await notion.create_inbox_item(
            contenido="[TEST] Item de prueba desde script",
            fuente=InboxFuente.TELEGRAM,
            notas="Creado desde test_notion_connection.py para validar el schema",
            confianza_ai=0.95,
        )
        if result:
            print(f"   ✓ Item creado: {result.get('id')}")
            print("   → Verifica en Notion que los campos estén correctos")
        else:
            print("   ✗ Error creando item - revisa los logs")
    else:
        print("   Omitido")
    print()

    # Test 9: Crear tarea de prueba
    print("9. Test de creación de Tarea")
    response = input("   ¿Crear tarea de prueba? (s/n): ").strip().lower()
    if response == "s":
        result = await notion.create_task(
            tarea="[TEST] Tarea de prueba desde script",
            contexto=TaskContexto.PERSONAL,
            estado=TaskEstado.BACKLOG,
            notas="Creada desde test_notion_connection.py",
        )
        if result:
            print(f"   ✓ Tarea creada: {result.get('id')}")
            print("   → Verifica en Notion que los campos estén correctos")
        else:
            print("   ✗ Error creando tarea - revisa los logs")
    else:
        print("   Omitido")
    print()

    # Resumen final
    print("=" * 60)
    print("                    RESUMEN")
    print("=" * 60)
    success_count = sum(1 for v in db_status.values() if v)
    total_count = len(db_status)
    print(f"Databases accesibles: {success_count}/{total_count}")
    if success_count == total_count:
        print("✓ Todas las databases están correctamente configuradas")
    else:
        print("⚠ Algunas databases no son accesibles - verifica los IDs y permisos")
    print()
    print("Campos verificados:")
    print("  - Tasks: Tarea, Contexto, Estado, Prioridad, etc.")
    print("  - Projects: Proyecto, Tipo, Estado, etc.")
    print("  - Nutrition: Fecha (Title), Desayuno, Comida, Cena, etc.")
    print("  - Workouts: Fecha (Title), Tipo, Ejercicios (JSON), etc.")
    print("  - Transactions: Concepto, Monto, Tipo, Categoría, etc.")
    print()
    print("=== Test completado ===")


if __name__ == "__main__":
    asyncio.run(main())
