"""AI Agents para Carlos Command."""

from app.agents.base import (
    get_dspy_lm,
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


__all__ = [
    # Base
    "get_dspy_lm",
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
]
