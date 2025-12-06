"""Initial schema - Brain V2

Revision ID: 001
Revises:
Create Date: 2024-12-06

Schema inicial con todas las tablas del Brain:
- user_profiles
- projects
- tasks
- reminders
- transactions
- debts
- workouts
- nutrition_logs
- conversation_history
- working_memory
- learned_patterns
- brain_metrics
- trigger_logs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Habilitar extension pgvector
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # user_profiles
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('telegram_chat_id', sa.String(50), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('timezone', sa.String(50), server_default='America/Mexico_City', nullable=False),
        sa.Column('work_start', sa.Time(), nullable=True),
        sa.Column('work_end', sa.Time(), nullable=True),
        sa.Column('work_days', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
        sa.Column('gym_days', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
        sa.Column('contexts', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
        sa.Column('default_context', sa.String(50), nullable=True),
        sa.Column('preferences', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'])

    # projects
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='active', nullable=False),
        sa.Column('type', sa.String(50), nullable=True),
        sa.Column('context', sa.String(50), nullable=True),
        sa.Column('progress', sa.Integer(), server_default='0', nullable=False),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'])
    op.create_index('ix_projects_status', 'projects', ['status'])

    # tasks
    op.create_table(
        'tasks',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=True),
        sa.Column('parent_task_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='backlog', nullable=False),
        sa.Column('priority', sa.String(20), server_default='normal', nullable=False),
        sa.Column('complexity', sa.String(20), nullable=True),
        sa.Column('context', sa.String(50), nullable=True),
        sa.Column('estimated_minutes', sa.Integer(), nullable=True),
        sa.Column('actual_minutes', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('blocked_by_task_id', sa.UUID(), nullable=True),
        sa.Column('blocked_by_external', sa.String(255), nullable=True),
        sa.Column('blocked_at', sa.DateTime(), nullable=True),
        sa.Column('recurrence_rule', sa.String(100), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parent_task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['blocked_by_task_id'], ['tasks.id'], ondelete='SET NULL')
    )
    op.create_index('ix_tasks_user_id', 'tasks', ['user_id'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_due_date', 'tasks', ['due_date'])
    op.create_index('ix_tasks_project_id', 'tasks', ['project_id'])

    # reminders
    op.create_table(
        'reminders',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('task_id', sa.UUID(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('priority', sa.String(20), server_default='normal', nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('snoozed_until', sa.DateTime(), nullable=True),
        sa.Column('snooze_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE')
    )
    op.create_index('ix_reminders_user_id', 'reminders', ['user_id'])
    op.create_index('ix_reminders_scheduled_at', 'reminders', ['scheduled_at'])
    op.create_index('ix_reminders_status', 'reminders', ['status'])

    # transactions
    op.create_table(
        'transactions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('is_recurring', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_transactions_date', 'transactions', ['date'])
    op.create_index('ix_transactions_category', 'transactions', ['category'])

    # debts
    op.create_table(
        'debts',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('creditor', sa.String(100), nullable=False),
        sa.Column('original_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('current_balance', sa.Numeric(12, 2), nullable=False),
        sa.Column('interest_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('monthly_payment', sa.Numeric(12, 2), nullable=True),
        sa.Column('due_day', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), server_default='active', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_debts_user_id', 'debts', ['user_id'])
    op.create_index('ix_debts_status', 'debts', ['status'])

    # workouts
    op.create_table(
        'workouts',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('exercises', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('feeling', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workouts_user_id', 'workouts', ['user_id'])
    op.create_index('ix_workouts_date', 'workouts', ['date'])

    # nutrition_logs
    op.create_table(
        'nutrition_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('meal_type', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('calories_estimate', sa.Integer(), nullable=True),
        sa.Column('protein_estimate', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_nutrition_logs_user_id', 'nutrition_logs', ['user_id'])
    op.create_index('ix_nutrition_logs_date', 'nutrition_logs', ['date'])

    # conversation_history
    op.create_table(
        'conversation_history',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tool_calls', postgresql.JSONB(), nullable=True),
        sa.Column('tool_results', postgresql.JSONB(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversation_history_user_id', 'conversation_history', ['user_id'])
    op.create_index('ix_conversation_history_created_at', 'conversation_history', ['created_at'])

    # working_memory
    op.create_table(
        'working_memory',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'key', name='uq_working_memory_user_key')
    )
    op.create_index('ix_working_memory_user_id', 'working_memory', ['user_id'])
    op.create_index('ix_working_memory_expires_at', 'working_memory', ['expires_at'])

    # learned_patterns
    op.create_table(
        'learned_patterns',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('pattern_type', sa.String(50), nullable=False),
        sa.Column('pattern_key', sa.String(255), nullable=False),
        sa.Column('pattern_value', postgresql.JSONB(), nullable=False),
        sa.Column('confidence', sa.Float(), server_default='0.5', nullable=False),
        sa.Column('occurrences', sa.Integer(), server_default='1', nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'pattern_type', 'pattern_key', name='uq_learned_patterns')
    )
    op.create_index('ix_learned_patterns_user_id', 'learned_patterns', ['user_id'])
    op.create_index('ix_learned_patterns_type', 'learned_patterns', ['pattern_type'])

    # brain_metrics
    op.create_table(
        'brain_metrics',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_brain_metrics_user_id', 'brain_metrics', ['user_id'])
    op.create_index('ix_brain_metrics_type', 'brain_metrics', ['metric_type'])
    op.create_index('ix_brain_metrics_created_at', 'brain_metrics', ['created_at'])

    # trigger_logs
    op.create_table(
        'trigger_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('trigger_name', sa.String(50), nullable=False),
        sa.Column('user_id', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('context', postgresql.JSONB(), nullable=True),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trigger_logs_trigger_name', 'trigger_logs', ['trigger_name'])
    op.create_index('ix_trigger_logs_created_at', 'trigger_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('trigger_logs')
    op.drop_table('brain_metrics')
    op.drop_table('learned_patterns')
    op.drop_table('working_memory')
    op.drop_table('conversation_history')
    op.drop_table('nutrition_logs')
    op.drop_table('workouts')
    op.drop_table('debts')
    op.drop_table('transactions')
    op.drop_table('reminders')
    op.drop_table('tasks')
    op.drop_table('projects')
    op.drop_table('user_profiles')
    op.execute('DROP EXTENSION IF EXISTS vector')
