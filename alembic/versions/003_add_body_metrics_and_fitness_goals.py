"""Add body_metrics and fitness_goals tables

Revision ID: 003
Revises: 002
Create Date: 2024-12-08

Agrega tablas para tracking de peso/métricas corporales y metas de fitness.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # BODY_METRICS - Métricas corporales (peso, grasa, medidas)
    # ============================================================
    op.create_table(
        'body_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user_profile.id'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')),

        # Medidas principales
        sa.Column('weight_kg', sa.Numeric(5, 2), nullable=False),
        sa.Column('body_fat_percentage', sa.Numeric(4, 1), nullable=True),
        sa.Column('muscle_mass_kg', sa.Numeric(5, 2), nullable=True),

        # Medidas secundarias
        sa.Column('waist_cm', sa.Numeric(5, 1), nullable=True),
        sa.Column('chest_cm', sa.Numeric(5, 1), nullable=True),
        sa.Column('arms_cm', sa.Numeric(5, 1), nullable=True),
        sa.Column('legs_cm', sa.Numeric(5, 1), nullable=True),

        # Contexto
        sa.Column('time_of_day', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.String(500), nullable=True),

        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
    )

    # Índice para búsquedas por usuario y fecha
    op.create_index('ix_body_metrics_user_date', 'body_metrics', ['user_id', 'date'])

    # ============================================================
    # FITNESS_GOALS - Metas de fitness/nutrición
    # ============================================================
    op.create_table(
        'fitness_goals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user_profile.id'), nullable=False),

        # Tipo de meta
        sa.Column('goal_type', sa.String(30), nullable=False),  # weight_loss, muscle_gain, maintenance

        # Valores
        sa.Column('target_value', sa.Numeric(5, 2), nullable=False),
        sa.Column('start_value', sa.Numeric(5, 2), nullable=False),
        sa.Column('current_value', sa.Numeric(5, 2), nullable=True),

        # Fechas
        sa.Column('start_date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')),
        sa.Column('target_date', sa.Date(), nullable=True),

        # Estado
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),

        # Macros objetivo
        sa.Column('daily_calories', sa.Integer(), nullable=True),
        sa.Column('daily_protein_g', sa.Integer(), nullable=True),
        sa.Column('daily_carbs_g', sa.Integer(), nullable=True),
        sa.Column('daily_fat_g', sa.Integer(), nullable=True),

        sa.Column('notes', sa.Text(), nullable=True),

        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    # Índice para buscar metas activas por usuario
    op.create_index('ix_fitness_goals_user_status', 'fitness_goals', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_fitness_goals_user_status', 'fitness_goals')
    op.drop_table('fitness_goals')

    op.drop_index('ix_body_metrics_user_date', 'body_metrics')
    op.drop_table('body_metrics')
