"""AI Agents para Carlos Command."""

from app.agents.base import (
    setup_dspy,
    MessageClassifier,
    TaskExtractor,
    ComplexityAnalyzer,
    SpendingAnalyzer as SpendingSignature,
    GenerateMorningPlan,
    AnalyzeNutrition,
)

from app.agents.inbox_processor import (
    InboxProcessorAgent,
    MessageCategory,
    ClassificationResult,
)

from app.agents.spending_analyzer import (
    SpendingAnalyzerAgent,
)

from app.agents.complexity_analyzer import (
    ComplexityAnalyzerAgent,
    Complexity,
    EnergyLevel as ComplexityEnergyLevel,
    ComplexityResult,
)

from app.agents.morning_planner import (
    MorningPlannerAgent,
    MorningPlanResult,
    TimeBlock,
)

from app.agents.nutrition_analyzer import (
    NutritionAnalyzerAgent,
    NutritionGoal,
    ActivityLevel,
    NutritionRating,
    NutritionResult,
    MealBreakdown,
)

from app.agents.workout_logger import (
    WorkoutLoggerAgent,
    WorkoutType,
    SessionRating,
    Exercise,
    ExerciseSet,
    WorkoutResult,
)

from app.agents.jira_helper import (
    JiraHelperAgent,
    JiraContentResult,
    UserStoryResult,
    quick_jira_update,
)

from app.agents.debt_strategist import (
    DebtStrategistAgent,
    Debt,
    PaymentStrategy,
    PaymentPlan,
    DebtStrategyResult,
)

from app.agents.study_balancer import (
    StudyBalancerAgent,
    StudyProject,
    StudySession,
    StudySuggestionResult,
    EnergyLevel as StudyEnergyLevel,
)

from app.agents.intent_router import (
    IntentRouterAgent,
    UserIntent,
    IntentResult,
    get_intent_router,
)

from app.agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorMode,
    UserContext,
    TaskPlanningResult,
    ProactiveNotification,
    get_orchestrator,
)

from app.agents.task_planner import (
    TaskPlannerAgent,
    TaskScheduleResult,
    DeadlineDetectionResult,
    Reminder,
    get_task_planner,
)

from app.agents.conversation_context import (
    ConversationContext,
    ConversationState,
    ConversationStore,
    ConversationMessage,
    ActiveEntity,
    PendingAction,
    EntityType,
    get_conversation_store,
)

from app.agents.conversational_orchestrator import (
    ConversationalOrchestrator,
    ConversationalResponse,
    get_conversational_orchestrator,
)

from app.agents.planning_assistant import (
    PlanningAssistant,
    TomorrowPlan,
    PrioritizationResult,
    RescheduleResult,
    get_planning_assistant,
)


__all__ = [
    # Base
    "setup_dspy",
    "MessageClassifier",
    "TaskExtractor",
    "ComplexityAnalyzer",
    "SpendingSignature",
    "GenerateMorningPlan",
    "AnalyzeNutrition",
    # Inbox Processor
    "InboxProcessorAgent",
    "MessageCategory",
    "ClassificationResult",
    # Spending Analyzer
    "SpendingAnalyzerAgent",
    # Complexity Analyzer
    "ComplexityAnalyzerAgent",
    "Complexity",
    "ComplexityEnergyLevel",
    "ComplexityResult",
    # Morning Planner
    "MorningPlannerAgent",
    "MorningPlanResult",
    "TimeBlock",
    # Nutrition Analyzer
    "NutritionAnalyzerAgent",
    "NutritionGoal",
    "ActivityLevel",
    "NutritionRating",
    "NutritionResult",
    "MealBreakdown",
    # Workout Logger
    "WorkoutLoggerAgent",
    "WorkoutType",
    "SessionRating",
    "Exercise",
    "ExerciseSet",
    "WorkoutResult",
    # Jira Helper
    "JiraHelperAgent",
    "JiraContentResult",
    "UserStoryResult",
    "quick_jira_update",
    # Debt Strategist
    "DebtStrategistAgent",
    "Debt",
    "PaymentStrategy",
    "PaymentPlan",
    "DebtStrategyResult",
    # Study Balancer
    "StudyBalancerAgent",
    "StudyProject",
    "StudySession",
    "StudySuggestionResult",
    "StudyEnergyLevel",
    # Intent Router
    "IntentRouterAgent",
    "UserIntent",
    "IntentResult",
    "get_intent_router",
    # Orchestrator
    "AgentOrchestrator",
    "OrchestratorMode",
    "UserContext",
    "TaskPlanningResult",
    "ProactiveNotification",
    "get_orchestrator",
    # Task Planner
    "TaskPlannerAgent",
    "TaskScheduleResult",
    "DeadlineDetectionResult",
    "Reminder",
    "get_task_planner",
    # Conversation Context
    "ConversationContext",
    "ConversationState",
    "ConversationStore",
    "ConversationMessage",
    "ActiveEntity",
    "PendingAction",
    "EntityType",
    "get_conversation_store",
    # Conversational Orchestrator
    "ConversationalOrchestrator",
    "ConversationalResponse",
    "get_conversational_orchestrator",
    # Planning Assistant
    "PlanningAssistant",
    "TomorrowPlan",
    "PrioritizationResult",
    "RescheduleResult",
    "get_planning_assistant",
]
