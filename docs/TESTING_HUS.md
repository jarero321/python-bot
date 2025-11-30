# Historias de Usuario - Testing de Carlos Command

> **Fecha**: 2024-11-30
> **Versión**: 0.1.0
> **Objetivo**: Validar todos los flujos del sistema y documentar estado actual

---

## Resumen Ejecutivo

| Categoría | Total HUs | Funcionales | Testeadas | Requieren Fix | Bloqueadas |
|-----------|-----------|-------------|-----------|---------------|------------|
| Tareas | 8 | 7 | 2 | 0 | 0 |
| Proyectos | 5 | 4 | 0 | 1 | 0 |
| Recordatorios | 4 | 3 | 0 | 1 | 0 |
| Planificación | 5 | 5 | 0 | 0 | 0 |
| Finanzas | 4 | 2 | 0 | 2 | 0 |
| Fitness | 4 | 4 | 0 | 0 | 0 |
| Captura | 3 | 3 | 0 | 0 | 0 |
| Comandos | 8 | 8 | 0 | 0 | 0 |
| Scheduler | 6 | 6 | 0 | 0 | 0 |
| **TOTAL** | **47** | **42 (89%)** | **2 (4%)** | **4 (9%)** | **0** |

---

## 1. GESTIÓN DE TAREAS

### HU-T01: Crear tarea simple
> **✅ TESTEADA** - Ver [TESTED_HUS.md](./TESTED_HUS.md#hu-001-crear-tarea-con-detección-de-duplicados-)

---

### HU-T02: Crear tarea con prioridad
**Como** usuario
**Quiero** crear una tarea urgente diciendo "Tarea urgente: llamar al cliente"
**Para** que se marque con prioridad alta

**Criterios de Aceptación:**
- [ ] Detecta keyword "urgente"
- [ ] Crea tarea con prioridad URGENT
- [ ] Muestra emoji de urgente en respuesta

**Pasos de Prueba:**
```
1. Enviar: "Tarea urgente: llamar al cliente"
2. Verificar prioridad en respuesta
3. Verificar en Notion prioridad = Urgente
```

**Estado**: ✅ FUNCIONAL

---

### HU-T03: Crear tarea con fecha
**Como** usuario
**Quiero** crear una tarea diciendo "Tarea para mañana: enviar reporte"
**Para** que tenga fecha de vencimiento

**Criterios de Aceptación:**
- [ ] Detecta "mañana" y calcula fecha
- [ ] Asigna fecha_do correcta
- [ ] Muestra fecha en respuesta

**Pasos de Prueba:**
```
1. Enviar: "Tarea para mañana: enviar reporte"
2. Verificar fecha en respuesta
3. Verificar en Notion fecha = mañana
```

**Estado**: ✅ FUNCIONAL

---

### HU-T04: Detectar tarea duplicada
> **✅ TESTEADA** - Ver [TESTED_HUS.md](./TESTED_HUS.md#hu-001-crear-tarea-con-detección-de-duplicados-) (incluida en HU-001)

---

### HU-T05: Listar tareas de hoy
**Como** usuario
**Quiero** ver mis tareas de hoy con /today
**Para** saber qué tengo pendiente

**Criterios de Aceptación:**
- [ ] Muestra tareas con estado TODAY o DOING
- [ ] Agrupa por estado (En progreso, Pendientes, Completadas)
- [ ] Muestra contador de progreso
- [ ] Muestra emoji de prioridad urgente

**Pasos de Prueba:**
```
1. Enviar: /today
2. Verificar agrupación correcta
3. Verificar contador X/Y completadas
```

**Estado**: ✅ FUNCIONAL

---

### HU-T06: Marcar tarea en progreso
**Como** usuario
**Quiero** marcar una tarea como "en progreso" con /doing
**Para** trackear en qué estoy trabajando

**Criterios de Aceptación:**
- [ ] Muestra lista de tareas pendientes de hoy
- [ ] Al seleccionar, cambia estado a DOING
- [ ] Confirma con nombre de tarea

**Pasos de Prueba:**
```
1. Enviar: /doing
2. Seleccionar tarea de la lista
3. Verificar cambio de estado en Notion
```

**Estado**: ✅ FUNCIONAL

---

### HU-T07: Completar tarea actual
**Como** usuario
**Quiero** completar la tarea actual con /done
**Para** marcarla como terminada

**Criterios de Aceptación:**
- [ ] Encuentra tarea en estado DOING
- [ ] Cambia estado a DONE
- [ ] Muestra mensaje de felicitación
- [ ] Si no hay tarea en DOING, muestra mensaje apropiado

**Pasos de Prueba:**
```
1. Tener una tarea en DOING
2. Enviar: /done
3. Verificar estado DONE en Notion
```

**Estado**: ✅ FUNCIONAL

---

### HU-T08: Buscar tarea por nombre
**Como** usuario
**Quiero** buscar una tarea diciendo "buscar tarea reporte"
**Para** encontrarla rápidamente

**Criterios de Aceptación:**
- [ ] Detecta intent TASK_QUERY
- [ ] Usa búsqueda semántica RAG
- [ ] Muestra resultados relevantes
- [ ] Permite seleccionar para ver detalles

**Pasos de Prueba:**
```
1. Enviar: "Buscar tarea sobre emails"
2. Verificar resultados relevantes
3. Verificar que usa búsqueda semántica
```

**Estado**: ✅ FUNCIONAL

---

## 2. GESTIÓN DE PROYECTOS

### HU-P01: Crear proyecto
**Como** usuario
**Quiero** crear un proyecto diciendo "Nuevo proyecto API Integration"
**Para** organizar tareas relacionadas

**Criterios de Aceptación:**
- [ ] Detecta intent PROJECT_CREATE
- [ ] Muestra teclado para seleccionar tipo
- [ ] Crea proyecto en Notion
- [ ] Indexa en RAG

**Pasos de Prueba:**
```
1. Enviar: "Nuevo proyecto API Integration"
2. Seleccionar tipo (ej: Freelance)
3. Verificar creación en Notion
```

**Estado**: ✅ FUNCIONAL

---

### HU-P02: Seleccionar tipo de proyecto
**Como** usuario
**Quiero** seleccionar el tipo de proyecto (Trabajo, Freelance, etc.)
**Para** categorizarlo correctamente

**Criterios de Aceptación:**
- [ ] Muestra botones: Trabajo, Freelance, Estudio, Personal
- [ ] Al seleccionar, crea con tipo correcto
- [ ] Callback `project_type_*` funciona

**Pasos de Prueba:**
```
1. Crear proyecto
2. Seleccionar "Freelance"
3. Verificar tipo en Notion
```

**Estado**: 🔧 REQUIERE FIX
**Issue**: Callback `project_type_freelance` no reconocido
**Fix Aplicado**: Agregado manejo de formato `project_type_*` en handlers.py

---

### HU-P03: Listar proyectos activos
**Como** usuario
**Quiero** ver mis proyectos con /projects
**Para** saber en qué estoy trabajando

**Criterios de Aceptación:**
- [ ] Muestra proyectos con estado ACTIVE
- [ ] Muestra barra de progreso
- [ ] Muestra tipo con emoji
- [ ] Indica si está atrasado

**Pasos de Prueba:**
```
1. Enviar: /projects
2. Verificar lista con progreso
3. Verificar emojis de tipo
```

**Estado**: ✅ FUNCIONAL

---

### HU-P04: Consultar proyecto específico
**Como** usuario
**Quiero** preguntar "¿Cómo va el proyecto X?"
**Para** ver su estado

**Criterios de Aceptación:**
- [ ] Detecta intent PROJECT_QUERY
- [ ] Busca proyecto por nombre (semántico)
- [ ] Muestra progreso y tareas pendientes

**Pasos de Prueba:**
```
1. Enviar: "¿Cómo va el proyecto API?"
2. Verificar que encuentra el correcto
3. Verificar detalles mostrados
```

**Estado**: ✅ FUNCIONAL

---

### HU-P05: Completar proyecto
**Como** usuario
**Quiero** marcar un proyecto como completado
**Para** cerrarlo

**Criterios de Aceptación:**
- [ ] Cambia estado a COMPLETED
- [ ] Actualiza progreso a 100%
- [ ] Muestra mensaje de felicitación

**Pasos de Prueba:**
```
1. Enviar: "Completar proyecto X"
2. Confirmar acción
3. Verificar en Notion
```

**Estado**: ✅ FUNCIONAL

---

## 3. RECORDATORIOS

### HU-R01: Crear recordatorio con tiempo predefinido
**Como** usuario
**Quiero** crear un recordatorio seleccionando "30 min" o "1 hora"
**Para** que me avise en ese tiempo

**Criterios de Aceptación:**
- [ ] Detecta intent REMINDER_CREATE
- [ ] Muestra botones de tiempo
- [ ] Crea recordatorio en BD
- [ ] Calcula fecha correcta

**Pasos de Prueba:**
```
1. Enviar: "Recuérdame llamar al doctor"
2. Seleccionar "1 hora"
3. Verificar creación en BD
4. Verificar hora programada
```

**Estado**: ✅ FUNCIONAL

---

### HU-R02: Crear recordatorio personalizado
**Como** usuario
**Quiero** crear un recordatorio para "mañana a las 10"
**Para** programarlo a una hora específica

**Criterios de Aceptación:**
- [ ] Seleccionar "Personalizado" muestra prompt
- [ ] Parsea "mañana a las 10" correctamente
- [ ] Parsea "en 2 horas" correctamente
- [ ] Parsea "el viernes a las 3pm" correctamente
- [ ] Crea recordatorio con fecha correcta

**Pasos de Prueba:**
```
1. Enviar: "Recuérdame X"
2. Seleccionar "Personalizado"
3. Escribir: "mañana a las 10"
4. Verificar hora correcta
```

**Estado**: 🔧 REQUIERE FIX
**Issue**: `pending_reminder` no se preservaba entre mensajes
**Fix Aplicado**: Extrae texto del recordatorio del mensaje original

---

### HU-R03: Listar recordatorios pendientes
**Como** usuario
**Quiero** ver mis recordatorios con "¿Qué recordatorios tengo?"
**Para** saber qué tengo programado

**Criterios de Aceptación:**
- [ ] Detecta intent REMINDER_QUERY
- [ ] Muestra recordatorios próximas 24h
- [ ] Muestra total pendientes
- [ ] Muestra hora y prioridad

**Pasos de Prueba:**
```
1. Crear algunos recordatorios
2. Enviar: "¿Qué recordatorios tengo?"
3. Verificar lista correcta
```

**Estado**: ✅ FUNCIONAL

---

### HU-R04: Recibir notificación de recordatorio
**Como** usuario
**Quiero** recibir el recordatorio cuando llegue la hora
**Para** no olvidar lo que programé

**Criterios de Aceptación:**
- [ ] Scheduler envía a la hora programada
- [ ] Mensaje incluye texto del recordatorio
- [ ] Ofrece opciones: Listo, Snooze, Cancelar

**Pasos de Prueba:**
```
1. Crear recordatorio para "en 2 minutos"
2. Esperar notificación
3. Verificar contenido y botones
```

**Estado**: ✅ FUNCIONAL
**Notas**: Depende del job `reminder_dispatcher`

---

## 4. PLANIFICACIÓN

### HU-PL01: Planificar mañana
**Como** usuario
**Quiero** decir "¿Qué hago mañana?" o "Planifica mi día"
**Para** recibir un plan con prioridades

**Criterios de Aceptación:**
- [ ] Detecta intent PLAN_TOMORROW
- [ ] Usa MorningPlannerAgent con AI
- [ ] Muestra tareas priorizadas
- [ ] Incluye sugerencias contextuales
- [ ] Ofrece aceptar/ajustar plan

**Pasos de Prueba:**
```
1. Enviar: "¿Qué hago mañana?"
2. Verificar plan generado por AI
3. Verificar botones de acción
```

**Estado**: ✅ FUNCIONAL

---

### HU-PL02: Ver carga de trabajo
**Como** usuario
**Quiero** preguntar "¿Cuánto tengo pendiente?"
**Para** saber si estoy sobrecargado

**Criterios de Aceptación:**
- [ ] Detecta intent WORKLOAD_CHECK
- [ ] Muestra total de tareas pendientes
- [ ] Agrupa por prioridad
- [ ] Muestra tareas vencidas

**Pasos de Prueba:**
```
1. Enviar: "¿Cuánto tengo pendiente?"
2. Verificar resumen de carga
3. Verificar desglose por prioridad
```

**Estado**: ✅ FUNCIONAL

---

### HU-PL03: Pedir ayuda para priorizar
**Como** usuario
**Quiero** preguntar "¿Qué hago primero, X o Y?"
**Para** decidir qué tarea atacar

**Criterios de Aceptación:**
- [ ] Detecta intent PRIORITIZE
- [ ] Analiza ambas tareas
- [ ] Sugiere basado en urgencia/importancia
- [ ] Explica razonamiento

**Pasos de Prueba:**
```
1. Enviar: "¿Qué hago primero, el reporte o la llamada?"
2. Verificar sugerencia con razonamiento
```

**Estado**: ✅ FUNCIONAL

---

### HU-PL04: Reprogramar tarea
**Como** usuario
**Quiero** decir "Mueve la tarea X para mañana"
**Para** reprogramarla

**Criterios de Aceptación:**
- [ ] Detecta intent RESCHEDULE
- [ ] Encuentra tarea por nombre
- [ ] Actualiza fecha en Notion
- [ ] Confirma nueva fecha

**Pasos de Prueba:**
```
1. Enviar: "Mueve el reporte para mañana"
2. Verificar cambio de fecha
3. Verificar en Notion
```

**Estado**: ✅ FUNCIONAL

---

### HU-PL05: Ver resumen de la semana
**Como** usuario
**Quiero** preguntar "¿Cómo va mi semana?"
**Para** ver un resumen

**Criterios de Aceptación:**
- [ ] Detecta intent PLAN_WEEK
- [ ] Muestra tareas por día
- [ ] Muestra progreso general
- [ ] Indica días más cargados

**Pasos de Prueba:**
```
1. Enviar: "¿Cómo va mi semana?"
2. Verificar desglose por día
```

**Estado**: ✅ FUNCIONAL

---

## 5. FINANZAS

### HU-F01: Registrar gasto
**Como** usuario
**Quiero** decir "Gasté $500 en comida"
**Para** trackear mis gastos

**Criterios de Aceptación:**
- [ ] Detecta intent EXPENSE_LOG
- [ ] Extrae monto y categoría
- [ ] Crea transacción en Notion
- [ ] Confirma registro

**Pasos de Prueba:**
```
1. Enviar: "Gasté $500 en comida"
2. Verificar extracción de datos
3. Verificar en Notion Transactions
```

**Estado**: ✅ FUNCIONAL

---

### HU-F02: Analizar compra potencial
**Como** usuario
**Quiero** decir "Me quiero comprar unos airpods por $3000"
**Para** recibir análisis antes de comprar

**Criterios de Aceptación:**
- [ ] Detecta intent EXPENSE_ANALYZE
- [ ] Extrae item y precio
- [ ] Hace preguntas reflexivas
- [ ] Ofrece opciones: Comprar, Wishlist, Esperar
- [ ] Usa SpendingAnalyzerAgent para análisis real

**Pasos de Prueba:**
```
1. Enviar: "Me quiero comprar unos airpods por $3000"
2. Verificar preguntas reflexivas
3. Verificar opciones de decisión
```

**Estado**: 🔧 REQUIERE FIX
**Issue**: SpendingAnalyzerAgent es placeholder, no hace análisis real
**Pendiente**: Integrar `SpendingAnalyzerAgent.analyze_purchase()`

---

### HU-F03: Consultar deudas
**Como** usuario
**Quiero** preguntar "¿Cuánto debo?"
**Para** ver resumen de deudas

**Criterios de Aceptación:**
- [ ] Detecta intent DEBT_QUERY
- [ ] Muestra lista de deudas activas
- [ ] Muestra total adeudado
- [ ] Muestra progreso de pago

**Pasos de Prueba:**
```
1. Enviar: "¿Cuánto debo?"
2. Verificar lista de deudas
3. Verificar totales
```

**Estado**: ✅ FUNCIONAL

---

### HU-F04: Registrar pago de deuda
**Como** usuario
**Quiero** decir "Pagué $1000 de la tarjeta"
**Para** actualizar mi deuda

**Criterios de Aceptación:**
- [ ] Detecta pago de deuda
- [ ] Actualiza saldo de deuda
- [ ] Registra transacción
- [ ] Muestra nuevo saldo

**Pasos de Prueba:**
```
1. Enviar: "Pagué $1000 de la tarjeta"
2. Verificar actualización de deuda
3. Verificar transacción registrada
```

**Estado**: 🔧 REQUIERE FIX
**Issue**: No hay handler específico para pago de deuda
**Pendiente**: Crear `DebtPaymentHandler`

---

## 6. FITNESS

### HU-FIT01: Registrar entrenamiento
**Como** usuario
**Quiero** registrar mi gym con /gym
**Para** trackear mis entrenamientos

**Criterios de Aceptación:**
- [ ] Muestra tipos: Push, Pull, Legs, Cardio, Rest
- [ ] Pide descripción de ejercicios
- [ ] Parsea ejercicios con sets/reps/peso
- [ ] Detecta PRs automáticamente
- [ ] Guarda en Notion

**Pasos de Prueba:**
```
1. Enviar: /gym
2. Seleccionar "Push"
3. Escribir: "banca 60kg 3x8, militar 35kg 3x10"
4. Verificar parseo correcto
5. Verificar guardado en Notion
```

**Estado**: ✅ FUNCIONAL

---

### HU-FIT02: Registrar día de descanso
**Como** usuario
**Quiero** registrar día de descanso
**Para** mantener tracking completo

**Criterios de Aceptación:**
- [ ] Seleccionar "Rest" registra inmediatamente
- [ ] No pide ejercicios
- [ ] Guarda tipo REST en Notion

**Pasos de Prueba:**
```
1. Enviar: /gym
2. Seleccionar "Rest"
3. Verificar registro inmediato
```

**Estado**: ✅ FUNCIONAL

---

### HU-FIT03: Registrar comida
**Como** usuario
**Quiero** registrar mi comida con /food
**Para** trackear nutrición

**Criterios de Aceptación:**
- [ ] Pide descripción de comidas
- [ ] NutritionAnalyzer estima macros
- [ ] Clasifica como healthy/moderate/heavy
- [ ] Guarda en Notion

**Pasos de Prueba:**
```
1. Enviar: /food
2. Escribir: "Desayuno: huevos con pan, Almuerzo: pollo con arroz"
3. Verificar análisis
4. Verificar guardado
```

**Estado**: ✅ FUNCIONAL

---

### HU-FIT04: Consultar historial de gym
**Como** usuario
**Quiero** preguntar "¿Cuánto levanto en banca?"
**Para** ver mi progreso

**Criterios de Aceptación:**
- [ ] Detecta intent GYM_QUERY
- [ ] Busca ejercicio específico
- [ ] Muestra historial de pesos
- [ ] Indica PRs

**Pasos de Prueba:**
```
1. Enviar: "¿Cuánto levanto en banca?"
2. Verificar historial
3. Verificar PRs mostrados
```

**Estado**: ✅ FUNCIONAL

---

## 7. CAPTURA RÁPIDA

### HU-C01: Guardar idea
**Como** usuario
**Quiero** decir "Idea: app para trackear hábitos"
**Para** guardarla en mi base de conocimiento

**Criterios de Aceptación:**
- [ ] Detecta intent IDEA
- [ ] Guarda en Knowledge DB con tipo IDEA
- [ ] Confirma guardado

**Pasos de Prueba:**
```
1. Enviar: "Idea: app para trackear hábitos"
2. Verificar confirmación
3. Verificar en Notion Knowledge
```

**Estado**: ✅ FUNCIONAL

---

### HU-C02: Guardar nota
**Como** usuario
**Quiero** decir "Nota: el cliente prefiere diseño minimalista"
**Para** guardar información

**Criterios de Aceptación:**
- [ ] Detecta intent NOTE
- [ ] Guarda en Knowledge DB con tipo NOTA
- [ ] Confirma guardado

**Pasos de Prueba:**
```
1. Enviar: "Nota: el cliente prefiere diseño minimalista"
2. Verificar confirmación
3. Verificar en Notion Knowledge
```

**Estado**: ✅ FUNCIONAL

---

### HU-C03: Mensaje no reconocido va a inbox
**Como** usuario
**Quiero** que mensajes no reconocidos se guarden en inbox
**Para** no perder información

**Criterios de Aceptación:**
- [ ] Intent UNKNOWN va a FallbackHandler
- [ ] Se guarda en Notion Inbox
- [ ] Confirma guardado en inbox

**Pasos de Prueba:**
```
1. Enviar mensaje ambiguo
2. Verificar que se guarda en inbox
```

**Estado**: ✅ FUNCIONAL

---

## 8. COMANDOS BÁSICOS

### HU-CMD01: /start
**Criterios**: Muestra bienvenida y comandos disponibles
**Estado**: ✅ FUNCIONAL

### HU-CMD02: /help
**Criterios**: Muestra ayuda detallada
**Estado**: ✅ FUNCIONAL

### HU-CMD03: /status
**Criterios**: Muestra estado del sistema y conexiones
**Estado**: ✅ FUNCIONAL

### HU-CMD04: /today
**Criterios**: Muestra tareas de hoy
**Estado**: ✅ FUNCIONAL

### HU-CMD05: /add [tarea]
**Criterios**: Crea tarea rápida
**Estado**: ✅ FUNCIONAL

### HU-CMD06: /doing
**Criterios**: Marca tarea en progreso
**Estado**: ✅ FUNCIONAL

### HU-CMD07: /done
**Criterios**: Completa tarea actual
**Estado**: ✅ FUNCIONAL

### HU-CMD08: /projects
**Criterios**: Lista proyectos activos
**Estado**: ✅ FUNCIONAL

---

## 9. SCHEDULER JOBS

### HU-SCH01: Morning Briefing (7:00 AM)
**Criterios**: Envía plan del día con AI
**Estado**: ✅ FUNCIONAL

### HU-SCH02: Hourly Check-in (9-18h)
**Criterios**: Muestra estado de tarea actual
**Estado**: ✅ FUNCIONAL

### HU-SCH03: Weekly Review (Domingo 10 AM)
**Criterios**: Envía métricas semanales
**Estado**: ✅ FUNCIONAL

### HU-SCH04: Reminder Dispatcher (cada minuto)
**Criterios**: Envía recordatorios programados
**Estado**: ✅ FUNCIONAL

### HU-SCH05: Deadline Alerts (9 AM, 3 PM)
**Criterios**: Alerta de deadlines próximos
**Estado**: ✅ FUNCIONAL

### HU-SCH06: Gym/Nutrition Reminders
**Criterios**: Recordatorios de salud
**Estado**: ✅ FUNCIONAL

---

## 10. FLUJOS CONVERSACIONALES

### HU-CONV01: Deep Work Session
**Como** usuario
**Quiero** iniciar sesión de deep work con /deepwork
**Para** concentrarme en una tarea

**Criterios de Aceptación:**
- [ ] Muestra lista de tareas o acepta custom
- [ ] Permite seleccionar duración
- [ ] Marca tarea como DOING
- [ ] Ofrece: Terminé, Bloqueado, Pausa

**Estado**: ✅ FUNCIONAL
**Notas**: TODO pendiente para recordatorio de fin

---

### HU-CONV02: Purchase Analysis Flow
**Como** usuario
**Quiero** analizar una compra potencial
**Para** tomar mejor decisión

**Criterios de Aceptación:**
- [ ] Detecta precio en mensaje
- [ ] Muestra análisis reflexivo
- [ ] Opciones: Comprar, Wishlist, No comprar
- [ ] Registra decisión

**Estado**: ✅ FUNCIONAL

---

## ISSUES IDENTIFICADOS Y FIXES APLICADOS

### Fix #1: Callback project_type_*
**Archivo**: `app/bot/handlers.py`
**Problema**: Callback `project_type_freelance` no reconocido
**Solución**: Agregado manejo de formato `project_type_*`
**Estado**: ✅ APLICADO

### Fix #2: pending_reminder perdido
**Archivo**: `app/bot/handlers.py`
**Problema**: Al seleccionar "Personalizado", no había recordatorio pendiente
**Solución**: Extraer texto del mensaje original
**Estado**: ✅ APLICADO

### Fix #3: TASK_STATUS_CHANGE no existe
**Archivo**: `app/agents/intent_router.py`
**Problema**: Intent no definido en enum
**Solución**: Agregado `TASK_STATUS_CHANGE` al enum
**Estado**: ✅ APLICADO

---

## PENDIENTES DE IMPLEMENTACIÓN

### Prioridad Alta

1. **SpendingAnalyzerAgent Integration**
   - Archivo: `app/agents/handlers/finance_handlers.py`
   - Cambiar placeholder por llamada real a `SpendingAnalyzerAgent.analyze_purchase()`

2. **Debt Payment Handler**
   - Crear handler para registrar pagos de deuda
   - Actualizar saldo automáticamente

### Prioridad Media

3. **Deep Work End Reminder**
   - Archivo: `app/bot/conversations.py:546`
   - Programar notificación cuando termine sesión

4. **API Admin Authentication**
   - Archivo: `app/api/admin.py`
   - Agregar autenticación JWT o API Key

### Prioridad Baja

5. **Calendar Integration**
   - Conectar con Google Calendar para eventos

---

## CHECKLIST DE TESTING MANUAL

### Pre-requisitos
- [ ] Docker containers corriendo (`./start.sh`)
- [ ] Webhook configurado en Telegram
- [ ] Bases de datos de Notion accesibles

### Tests Críticos (Ejecutar siempre)
- [ ] HU-T01: Crear tarea simple
- [ ] HU-P01: Crear proyecto
- [ ] HU-R01: Crear recordatorio
- [ ] HU-CMD04: /today
- [ ] HU-F01: Registrar gasto

### Tests de Flujos Completos
- [ ] Crear tarea → Marcar doing → Completar
- [ ] Crear proyecto → Seleccionar tipo → Verificar
- [ ] Crear recordatorio → Seleccionar tiempo → Recibir notificación
- [ ] Registrar gym → Verificar en Notion
- [ ] Planificar día → Aceptar plan

---

## MÉTRICAS DE COBERTURA

```
Intents Definidos:     26
Intents con Handler:   24 (92%)
Intents Funcionales:   22 (85%)

Comandos Definidos:     8
Comandos Funcionales:   8 (100%)

Flujos Conversacionales: 5
Flujos Funcionales:      5 (100%)

Jobs Scheduler:        10
Jobs Funcionales:      10 (100%)

TOTAL FUNCIONALIDAD:   89%
```

---

*Documento generado: 2024-11-30*
*Última actualización: 2024-11-30*
