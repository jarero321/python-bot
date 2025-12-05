"""Pytest configuration and fixtures for Carlos Command tests."""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set test environment
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
os.environ["TELEGRAM_CHAT_ID"] = "test_chat_id"
os.environ["NOTION_API_KEY"] = "test_notion_key"
os.environ["GEMINI_API_KEY"] = "test_gemini_key"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///data/test.db"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_telegram_service():
    """Mock TelegramService for tests."""
    with patch("app.services.telegram.TelegramService") as mock:
        service = MagicMock()
        service.send_message = AsyncMock(return_value=True)
        service.send_message_with_keyboard = AsyncMock(return_value=True)
        mock.return_value = service
        yield service


@pytest.fixture
def mock_notion_service():
    """Mock NotionService for tests."""
    with patch("app.services.notion.NotionService") as mock:
        service = MagicMock()

        # Mock common methods
        service.get_tasks_for_today = AsyncMock(return_value=[])
        service.get_pending_tasks = AsyncMock(return_value=[])
        service.get_active_projects = AsyncMock(return_value=[])
        service.create_task = AsyncMock(return_value={"id": "test_task_id"})
        service.update_task = AsyncMock(return_value=True)
        service.test_connection = AsyncMock(return_value=True)

        mock.return_value = service
        yield service


@pytest.fixture
def mock_gemini():
    """Mock Gemini/DSPy LLM for tests."""
    with patch("dspy.LM") as mock:
        lm = MagicMock()
        mock.return_value = lm
        yield lm


@pytest.fixture
def sample_task():
    """Sample task data for testing."""
    return {
        "id": "test_task_123",
        "title": "Test Task",
        "description": "This is a test task",
        "status": "today",
        "priority": "normal",
        "due_date": "2024-12-01",
        "project_id": None,
        "created_at": "2024-11-28T10:00:00Z",
    }


@pytest.fixture
def sample_project():
    """Sample project data for testing."""
    return {
        "id": "test_project_123",
        "name": "Test Project",
        "type": "work",
        "status": "active",
        "progress": 50,
        "target_date": "2024-12-31",
    }


@pytest.fixture
def sample_reminder():
    """Sample reminder data for testing."""
    return {
        "id": 1,
        "message": "Test reminder",
        "remind_at": "2024-11-28T14:00:00",
        "user_id": "test_user",
        "status": "pending",
    }


@pytest.fixture
def sample_workout():
    """Sample workout data for testing."""
    return {
        "date": "2024-11-28",
        "type": "push",
        "exercises": [
            {"name": "Bench Press", "sets": 3, "reps": 8, "weight": 60},
            {"name": "Shoulder Press", "sets": 3, "reps": 10, "weight": 35},
        ],
        "feeling": "good",
        "notes": "Great session",
    }


@pytest.fixture
def sample_nutrition():
    """Sample nutrition data for testing."""
    return {
        "date": "2024-11-28",
        "meals": [
            {"type": "breakfast", "description": "3 eggs with toast", "calories": 450},
            {"type": "lunch", "description": "Chicken with rice", "calories": 650},
            {"type": "dinner", "description": "Salmon with vegetables", "calories": 550},
        ],
        "total_calories": 1650,
        "protein": 120,
    }


@pytest.fixture
def sample_spending_context():
    """Sample financial context for spending analysis."""
    return {
        "monthly_budget": 15000.0,
        "current_debt": 330000.0,
        "remaining_budget": 8500.0,
    }


# ==================== TEST CLIENT ====================

@pytest.fixture
def test_client(mock_telegram_service, mock_notion_service, mock_gemini):
    """Create a test client for the FastAPI app."""
    # Import here to avoid loading before mocks are set up
    from app.main import app
    return TestClient(app)


# ==================== ASYNC FIXTURES ====================

@pytest.fixture
async def async_mock_telegram():
    """Async mock for Telegram service."""
    mock = AsyncMock()
    mock.send_message.return_value = True
    mock.send_message_with_keyboard.return_value = True
    return mock


@pytest.fixture
async def async_mock_notion():
    """Async mock for Notion service."""
    mock = AsyncMock()
    mock.get_tasks_for_today.return_value = []
    mock.get_pending_tasks.return_value = []
    mock.create_task.return_value = {"id": "new_task_id"}
    return mock
