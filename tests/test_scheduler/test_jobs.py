"""Tests for scheduler jobs."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, date


class TestMorningBriefingJob:
    """Test suite for morning briefing job."""

    @pytest.mark.asyncio
    async def test_morning_briefing_sends_message(self):
        """Test that morning briefing sends a message."""
        with patch("app.scheduler.jobs.morning_briefing.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.morning_briefing.get_notion_service") as mock_notion:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_notion.return_value.get_tasks_for_today = AsyncMock(return_value=[
                    {"title": "Task 1", "priority": "alta"},
                    {"title": "Task 2", "priority": "normal"},
                ])
                mock_notion.return_value.get_pending_tasks = AsyncMock(return_value=[])

                from app.scheduler.jobs.morning_briefing import morning_briefing_job

                await morning_briefing_job()

                mock_telegram.return_value.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_morning_briefing_no_tasks(self):
        """Test morning briefing when there are no tasks."""
        with patch("app.scheduler.jobs.morning_briefing.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.morning_briefing.get_notion_service") as mock_notion:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_notion.return_value.get_tasks_for_today = AsyncMock(return_value=[])
                mock_notion.return_value.get_pending_tasks = AsyncMock(return_value=[])

                from app.scheduler.jobs.morning_briefing import morning_briefing_job

                await morning_briefing_job()

                # Should still send a message even with no tasks
                mock_telegram.return_value.send_message.assert_called()


class TestHourlyCheckinJob:
    """Test suite for hourly check-in job."""

    @pytest.mark.asyncio
    async def test_hourly_checkin_with_active_task(self):
        """Test check-in when there's an active task."""
        with patch("app.scheduler.jobs.hourly_checkin.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.hourly_checkin.get_notion_service") as mock_notion:
                mock_telegram.return_value.send_message_with_keyboard = AsyncMock(return_value=True)
                mock_notion.return_value.get_active_task = AsyncMock(return_value={
                    "id": "task_123",
                    "title": "Working on feature",
                    "status": "doing",
                })

                from app.scheduler.jobs.hourly_checkin import hourly_checkin_job

                await hourly_checkin_job()

                mock_telegram.return_value.send_message_with_keyboard.assert_called()

    @pytest.mark.asyncio
    async def test_hourly_checkin_no_active_task(self):
        """Test check-in when there's no active task."""
        with patch("app.scheduler.jobs.hourly_checkin.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.hourly_checkin.get_notion_service") as mock_notion:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_notion.return_value.get_active_task = AsyncMock(return_value=None)

                from app.scheduler.jobs.hourly_checkin import hourly_checkin_job

                await hourly_checkin_job()

                # Should prompt to start a task
                mock_telegram.return_value.send_message.assert_called()


class TestGymReminderJob:
    """Test suite for gym reminder job."""

    @pytest.mark.asyncio
    async def test_gym_reminder_gentle(self):
        """Test gentle gym reminder."""
        with patch("app.scheduler.jobs.gym_reminder.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.gym_reminder.get_notion_service") as mock_notion:
                mock_telegram.return_value.send_message_with_keyboard = AsyncMock(return_value=True)
                mock_notion.return_value.get_today_workout = AsyncMock(return_value=None)

                from app.scheduler.jobs.gym_reminder import gym_reminder_job

                await gym_reminder_job(escalation_level="gentle")

                mock_telegram.return_value.send_message_with_keyboard.assert_called()

    @pytest.mark.asyncio
    async def test_gym_reminder_already_logged(self):
        """Test gym reminder when workout already logged."""
        with patch("app.scheduler.jobs.gym_reminder.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.gym_reminder.get_notion_service") as mock_notion:
                mock_notion.return_value.get_today_workout = AsyncMock(return_value={
                    "id": "workout_123",
                    "type": "push",
                })

                from app.scheduler.jobs.gym_reminder import gym_reminder_job

                await gym_reminder_job(escalation_level="gentle")

                # Should not send reminder if already logged
                mock_telegram.return_value.send_message_with_keyboard.assert_not_called()


class TestNutritionReminderJob:
    """Test suite for nutrition reminder job."""

    @pytest.mark.asyncio
    async def test_nutrition_reminder_sends(self):
        """Test nutrition reminder is sent."""
        with patch("app.scheduler.jobs.nutrition_reminder.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.nutrition_reminder.get_notion_service") as mock_notion:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_notion.return_value.get_today_nutrition = AsyncMock(return_value=None)

                from app.scheduler.jobs.nutrition_reminder import nutrition_reminder_job

                await nutrition_reminder_job()

                mock_telegram.return_value.send_message.assert_called()


class TestWeeklyReviewJob:
    """Test suite for weekly review job."""

    @pytest.mark.asyncio
    async def test_weekly_review_generates_summary(self):
        """Test weekly review generates summary."""
        with patch("app.scheduler.jobs.weekly_review.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.weekly_review.get_notion_service") as mock_notion:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_notion.return_value.get_completed_tasks_this_week = AsyncMock(return_value=[
                    {"title": "Task 1"},
                    {"title": "Task 2"},
                ])
                mock_notion.return_value.get_workouts_this_week = AsyncMock(return_value=[
                    {"type": "push"},
                    {"type": "pull"},
                ])

                from app.scheduler.jobs.weekly_review import weekly_review_job

                await weekly_review_job()

                mock_telegram.return_value.send_message.assert_called()
                call_args = mock_telegram.return_value.send_message.call_args
                message = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
                # Should contain summary info
                assert "2" in message or "tareas" in message.lower()


class TestReminderDispatcherJob:
    """Test suite for reminder dispatcher job."""

    @pytest.mark.asyncio
    async def test_dispatch_pending_reminders(self):
        """Test dispatching pending reminders."""
        with patch("app.scheduler.jobs.reminder_dispatcher.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.reminder_dispatcher.ReminderRepository") as mock_repo:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_repo.return_value.get_due_reminders = AsyncMock(return_value=[
                    {"id": 1, "message": "Call doctor", "remind_at": datetime.now()},
                ])
                mock_repo.return_value.mark_as_sent = AsyncMock()

                from app.scheduler.jobs.reminder_dispatcher import dispatch_pending_reminders

                await dispatch_pending_reminders()

                mock_telegram.return_value.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_no_pending_reminders(self):
        """Test dispatcher with no pending reminders."""
        with patch("app.scheduler.jobs.reminder_dispatcher.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.reminder_dispatcher.ReminderRepository") as mock_repo:
                mock_repo.return_value.get_due_reminders = AsyncMock(return_value=[])

                from app.scheduler.jobs.reminder_dispatcher import dispatch_pending_reminders

                await dispatch_pending_reminders()

                mock_telegram.return_value.send_message.assert_not_called()


class TestRagSyncJob:
    """Test suite for RAG sync job."""

    @pytest.mark.asyncio
    async def test_rag_sync_indexes_new_tasks(self):
        """Test RAG sync indexes new tasks."""
        with patch("app.scheduler.jobs.rag_sync.get_task_service") as mock_task_service:
            with patch("app.scheduler.jobs.rag_sync.get_retriever") as mock_retriever:
                mock_task_service.return_value.get_recently_updated = AsyncMock(return_value=[
                    MagicMock(id="task_1", title="New task"),
                ])
                mock_retriever.return_value.index_task = AsyncMock()

                from app.scheduler.jobs.rag_sync import sync_rag_index_job

                await sync_rag_index_job()

                mock_retriever.return_value.index_task.assert_called()


class TestMetricsSyncJob:
    """Test suite for metrics sync job."""

    @pytest.mark.asyncio
    async def test_daily_metrics_summary(self):
        """Test daily metrics summary is sent."""
        with patch("app.scheduler.jobs.metrics_sync.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.metrics_sync.get_metrics_collector") as mock_collector:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_collector.return_value.get_summary.return_value = {
                    "uptime_human": "12:30:45",
                    "endpoints": {
                        "total_calls": 100,
                        "unique_endpoints": 5,
                        "slowest": [],
                    },
                    "agents": {
                        "total_calls": 50,
                        "success_rate": 95.0,
                        "unique_agents": 8,
                        "slowest": [],
                    },
                }

                from app.scheduler.jobs.metrics_sync import send_daily_metrics_summary

                await send_daily_metrics_summary()

                mock_telegram.return_value.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_performance_alert_no_issues(self):
        """Test performance alert with no issues."""
        with patch("app.scheduler.jobs.metrics_sync.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.metrics_sync.get_metrics_collector") as mock_collector:
                mock_collector.return_value.get_endpoint_metrics.return_value = [
                    {"path": "/health", "avg_time_ms": 50, "error_rate": 0},
                ]
                mock_collector.return_value.get_agent_metrics.return_value = [
                    {"agent_name": "IntentRouter", "avg_time_ms": 500, "success_rate": 98},
                ]

                from app.scheduler.jobs.metrics_sync import send_performance_alert

                await send_performance_alert()

                # Should not send alert if no issues
                mock_telegram.return_value.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_performance_alert_slow_endpoint(self):
        """Test performance alert with slow endpoint."""
        with patch("app.scheduler.jobs.metrics_sync.get_telegram_service") as mock_telegram:
            with patch("app.scheduler.jobs.metrics_sync.get_metrics_collector") as mock_collector:
                mock_telegram.return_value.send_message = AsyncMock(return_value=True)
                mock_collector.return_value.get_endpoint_metrics.return_value = [
                    {"path": "/slow", "avg_time_ms": 5000, "error_rate": 0},
                ]
                mock_collector.return_value.get_agent_metrics.return_value = []

                from app.scheduler.jobs.metrics_sync import send_performance_alert

                await send_performance_alert()

                mock_telegram.return_value.send_message.assert_called()
