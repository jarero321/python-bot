"""Tests for SpendingAnalyzerAgent."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.agents.spending_analyzer import (
    SpendingAnalyzerAgent,
    SpendingAnalysisResult,
    SpendingRecommendation,
    BudgetImpact,
)


class TestSpendingAnalyzerAgent:
    """Test suite for SpendingAnalyzerAgent."""

    @pytest.fixture
    def agent(self):
        """Create agent with mocked DSPy."""
        with patch("app.agents.base.setup_dspy"):
            with patch("dspy.ChainOfThought") as mock_cot:
                mock_module = MagicMock()
                mock_cot.return_value = mock_module
                agent = SpendingAnalyzerAgent(
                    monthly_budget=15000.0,
                    current_debt=330000.0,
                )
                agent.analyzer = mock_module
                return agent

    def test_extract_amount_pesos(self, agent):
        """Test extracting amount with peso sign."""
        assert agent._extract_amount("Quiero comprar algo por $1,500") == 1500.0
        assert agent._extract_amount("Cuesta $2500 pesos") == 2500.0
        assert agent._extract_amount("$3,000.00 MXN") == 3000.0

    def test_extract_amount_text(self, agent):
        """Test extracting amount with text indicators."""
        assert agent._extract_amount("Son 1500 pesos") == 1500.0
        assert agent._extract_amount("Cuesta 2000 mxn") == 2000.0

    def test_extract_amount_none(self, agent):
        """Test when no amount is found."""
        assert agent._extract_amount("Quiero comprar algo") is None
        assert agent._extract_amount("Es muy caro") is None

    def test_calculate_budget_impact_minimal(self, agent):
        """Test minimal budget impact (<5%)."""
        result = agent._calculate_budget_impact(500, 15000)
        assert result == BudgetImpact.MINIMAL

    def test_calculate_budget_impact_moderate(self, agent):
        """Test moderate budget impact (5-15%)."""
        result = agent._calculate_budget_impact(1500, 15000)
        assert result == BudgetImpact.MODERATE

    def test_calculate_budget_impact_significant(self, agent):
        """Test significant budget impact (15-30%)."""
        result = agent._calculate_budget_impact(3000, 15000)
        assert result == BudgetImpact.SIGNIFICANT

    def test_calculate_budget_impact_critical(self, agent):
        """Test critical budget impact (>30%)."""
        result = agent._calculate_budget_impact(6000, 15000)
        assert result == BudgetImpact.CRITICAL

    def test_calculate_recommendation_buy(self, agent):
        """Test BUY recommendation."""
        result = agent._calculate_recommendation(9, BudgetImpact.MINIMAL)
        assert result == SpendingRecommendation.BUY

    def test_calculate_recommendation_wait(self, agent):
        """Test WAIT recommendation."""
        result = agent._calculate_recommendation(7, BudgetImpact.SIGNIFICANT)
        assert result == SpendingRecommendation.WAIT

    def test_calculate_recommendation_wishlist(self, agent):
        """Test WISHLIST recommendation."""
        result = agent._calculate_recommendation(5, BudgetImpact.SIGNIFICANT)
        assert result == SpendingRecommendation.WISHLIST

    def test_calculate_recommendation_skip(self, agent):
        """Test SKIP recommendation."""
        result = agent._calculate_recommendation(2, BudgetImpact.CRITICAL)
        assert result == SpendingRecommendation.SKIP

    def test_parse_questions_pipe_separator(self, agent):
        """Test parsing questions with pipe separator."""
        questions = agent._parse_questions(
            "¿Lo necesitas?|¿Puedes esperar?|¿Mejora tu vida?"
        )
        assert len(questions) == 3
        assert "¿Lo necesitas?" in questions

    def test_parse_questions_newline_separator(self, agent):
        """Test parsing questions with newline separator."""
        questions = agent._parse_questions(
            "¿Lo necesitas?\n¿Puedes esperar?\n¿Mejora tu vida?"
        )
        assert len(questions) == 3

    def test_parse_questions_question_mark_separator(self, agent):
        """Test parsing questions with question mark separator."""
        questions = agent._parse_questions(
            "¿Lo necesitas? ¿Puedes esperar? ¿Mejora tu vida?"
        )
        assert len(questions) == 3

    def test_calculate_debt_impact_no_debt(self, agent):
        """Test debt impact with no debt."""
        result = agent._calculate_debt_impact(1000, 0)
        assert "sin deuda" in result.lower()

    def test_calculate_debt_impact_significant(self, agent):
        """Test significant debt impact."""
        result = agent._calculate_debt_impact(33000, 330000)
        assert "10" in result  # 10% of debt

    def test_calculate_debt_impact_minimal(self, agent):
        """Test minimal debt impact."""
        result = agent._calculate_debt_impact(1000, 330000)
        assert "mínimo" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_success(self, agent):
        """Test successful execution."""
        # Mock analyzer response
        agent.analyzer.return_value = MagicMock(
            necessity_score="7",
            budget_impact="moderate",
            recommendation="wait",
            honest_questions="¿Lo necesitas?|¿Puedes esperar?",
        )

        result = await agent.execute("Quiero comprar unos AirPods por $3000")

        assert isinstance(result, SpendingAnalysisResult)
        assert result.amount == 3000.0
        assert result.necessity_score == 7
        assert result.budget_impact == BudgetImpact.MODERATE
        assert result.recommendation == SpendingRecommendation.WAIT
        assert len(result.honest_questions) == 2

    @pytest.mark.asyncio
    async def test_execute_no_amount(self, agent):
        """Test execution with no amount in message."""
        agent.analyzer.return_value = MagicMock(
            necessity_score="5",
            budget_impact="minimal",
            recommendation="wishlist",
            honest_questions="¿Lo necesitas?",
        )

        result = await agent.execute("Quiero comprar algo caro")

        assert result.amount == 0.0

    def test_format_analysis_message(self, agent):
        """Test formatting analysis result as message."""
        result = SpendingAnalysisResult(
            amount=3000.0,
            necessity_score=7,
            budget_impact=BudgetImpact.MODERATE,
            recommendation=SpendingRecommendation.WAIT,
            honest_questions=["¿Lo necesitas?", "¿Puedes esperar?"],
            budget_after_purchase=12000.0,
            debt_payment_impact="Representa 0.9% de tu deuda",
        )

        message = agent.format_analysis_message(result)

        assert "$3,000.00" in message
        assert "7/10" in message
        assert "Moderate" in message
        assert "Esperar" in message
        assert "$12,000.00" in message
        assert "¿Lo necesitas?" in message

    def test_set_financial_context(self, agent):
        """Test updating financial context."""
        agent.set_financial_context(
            monthly_budget=20000.0,
            current_debt=250000.0,
        )

        assert agent.monthly_budget == 20000.0
        assert agent.current_debt == 250000.0
