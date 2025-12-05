"""Tests for IntentRouterAgent."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Import after mocking to avoid DSPy initialization
with patch("app.agents.base.setup_dspy"):
    from app.agents.intent_router import (
        IntentRouterAgent,
        UserIntent,
    )


class TestIntentRouterAgent:
    """Test suite for IntentRouterAgent."""

    @pytest.fixture
    def agent(self):
        """Create agent with mocked DSPy."""
        with patch("app.agents.base.setup_dspy"):
            with patch("dspy.ChainOfThought") as mock_cot:
                mock_module = MagicMock()
                mock_cot.return_value = mock_module
                agent = IntentRouterAgent()
                agent.router = mock_module
                return agent

    @pytest.fixture
    def mock_router_response(self):
        """Create a mock router response."""
        def create_response(intent: str, confidence: float = 0.9, entities: str = ""):
            response = MagicMock()
            response.intent = intent
            response.confidence = confidence
            response.entities = entities
            return response
        return create_response

    @pytest.mark.asyncio
    async def test_route_greeting(self, agent, mock_router_response):
        """Test routing greeting messages."""
        agent.router.return_value = mock_router_response("GREETING")

        result = await agent.execute("Hola, buenos días")

        assert result.intent == UserIntent.GREETING
        assert result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_route_task_create(self, agent, mock_router_response):
        """Test routing task creation messages."""
        agent.router.return_value = mock_router_response(
            "TASK_CREATE",
            entities="title:revisar reporte|priority:alta"
        )

        result = await agent.execute("Crear tarea: revisar el reporte urgente")

        assert result.intent == UserIntent.TASK_CREATE

    @pytest.mark.asyncio
    async def test_route_task_query(self, agent, mock_router_response):
        """Test routing task query messages."""
        agent.router.return_value = mock_router_response("TASK_QUERY")

        result = await agent.execute("¿Qué tareas tengo pendientes?")

        assert result.intent == UserIntent.TASK_QUERY

    @pytest.mark.asyncio
    async def test_route_expense_analyze(self, agent, mock_router_response):
        """Test routing expense analysis messages."""
        agent.router.return_value = mock_router_response(
            "EXPENSE_ANALYZE",
            entities="item:AirPods|amount:3000"
        )

        result = await agent.execute("Quiero comprar unos AirPods por $3000")

        assert result.intent == UserIntent.EXPENSE_ANALYZE

    @pytest.mark.asyncio
    async def test_route_gym_log(self, agent, mock_router_response):
        """Test routing gym logging messages."""
        agent.router.return_value = mock_router_response("GYM_LOG")

        result = await agent.execute("Fui al gym, hice pecho: banca 60kg 3x8")

        assert result.intent == UserIntent.GYM_LOG

    @pytest.mark.asyncio
    async def test_route_reminder_create(self, agent, mock_router_response):
        """Test routing reminder creation messages."""
        agent.router.return_value = mock_router_response(
            "REMINDER_CREATE",
            entities="message:llamar al doctor|time:2 horas"
        )

        result = await agent.execute("Recuérdame llamar al doctor en 2 horas")

        assert result.intent == UserIntent.REMINDER_CREATE

    @pytest.mark.asyncio
    async def test_route_debt_query(self, agent, mock_router_response):
        """Test routing debt query messages."""
        agent.router.return_value = mock_router_response("DEBT_QUERY")

        result = await agent.execute("¿Cuánto debo en total?")

        assert result.intent == UserIntent.DEBT_QUERY

    @pytest.mark.asyncio
    async def test_route_unknown(self, agent, mock_router_response):
        """Test routing unknown messages."""
        agent.router.return_value = mock_router_response("UNKNOWN", confidence=0.3)

        result = await agent.execute("asdfghjkl")

        assert result.intent == UserIntent.UNKNOWN

    @pytest.mark.asyncio
    async def test_low_confidence_fallback(self, agent, mock_router_response):
        """Test fallback when confidence is low."""
        agent.router.return_value = mock_router_response("TASK_CREATE", confidence=0.2)

        result = await agent.execute("quizás hacer algo")

        # With low confidence, might fallback to UNKNOWN
        assert result.confidence < 0.5

    @pytest.mark.asyncio
    async def test_context_usage(self, agent, mock_router_response):
        """Test that context is passed to router."""
        agent.router.return_value = mock_router_response("TASK_UPDATE")

        context = "Usuario estaba viendo tarea 'revisar reporte'"
        result = await agent.execute(
            "Marca esa como completada",
            context=context
        )

        # Verify router was called with context
        agent.router.assert_called_once()
        call_args = agent.router.call_args
        assert "context" in call_args.kwargs or len(call_args.args) > 1


class TestUserIntent:
    """Test UserIntent enum."""

    def test_all_intents_defined(self):
        """Test that all expected intents are defined."""
        expected_intents = [
            "GREETING",
            "HELP",
            "STATUS",
            "TASK_CREATE",
            "TASK_QUERY",
            "TASK_UPDATE",
            "TASK_DELETE",
            "PROJECT_CREATE",
            "PROJECT_QUERY",
            "REMINDER_CREATE",
            "REMINDER_QUERY",
            "EXPENSE_ANALYZE",
            "EXPENSE_LOG",
            "DEBT_QUERY",
            "GYM_LOG",
            "GYM_QUERY",
            "NUTRITION_LOG",
            "NUTRITION_QUERY",
            "PLAN_TOMORROW",
            "PLAN_WEEK",
            "IDEA",
            "NOTE",
            "UNKNOWN",
        ]

        for intent_name in expected_intents:
            assert hasattr(UserIntent, intent_name), f"Missing intent: {intent_name}"

    def test_intent_values_are_lowercase(self):
        """Test that intent values are lowercase."""
        for intent in UserIntent:
            assert intent.value == intent.value.lower()
