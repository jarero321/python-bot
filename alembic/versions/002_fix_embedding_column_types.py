"""Fix embedding column types from double precision[] to vector(768)

Revision ID: 002
Revises: 001
Create Date: 2024-12-07

La migración inicial creó las columnas embedding como ARRAY(Float)
pero deberían ser vector(768) para usar pgvector correctamente.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Asegurar que pgvector está habilitado
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # ============================================================
    # TASKS - Columna embedding
    # ============================================================
    # Eliminar columna incorrecta (double precision[])
    op.drop_column('tasks', 'embedding')
    # Crear columna correcta (vector(768))
    op.execute('ALTER TABLE tasks ADD COLUMN embedding vector(768)')
    # Índice para búsqueda por similitud coseno (ivfflat es más rápido para datasets pequeños)
    op.execute('''
        CREATE INDEX ix_tasks_embedding
        ON tasks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')

    # ============================================================
    # PROJECTS - Columna embedding
    # ============================================================
    op.drop_column('projects', 'embedding')
    op.execute('ALTER TABLE projects ADD COLUMN embedding vector(768)')
    op.execute('''
        CREATE INDEX ix_projects_embedding
        ON projects
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')

    # ============================================================
    # TRANSACTIONS - Columna embedding
    # ============================================================
    op.drop_column('transactions', 'embedding')
    op.execute('ALTER TABLE transactions ADD COLUMN embedding vector(768)')
    op.execute('''
        CREATE INDEX ix_transactions_embedding
        ON transactions
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')

    # ============================================================
    # CONVERSATION_HISTORY - Columna embedding
    # ============================================================
    op.drop_column('conversation_history', 'embedding')
    op.execute('ALTER TABLE conversation_history ADD COLUMN embedding vector(768)')
    op.execute('''
        CREATE INDEX ix_conversation_history_embedding
        ON conversation_history
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')


def downgrade() -> None:
    # Revertir a double precision[] (perderá datos de embeddings)

    # conversation_history
    op.execute('DROP INDEX IF EXISTS ix_conversation_history_embedding')
    op.drop_column('conversation_history', 'embedding')
    op.add_column('conversation_history',
        sa.Column('embedding', sa.ARRAY(sa.Float()), nullable=True)
    )

    # transactions
    op.execute('DROP INDEX IF EXISTS ix_transactions_embedding')
    op.drop_column('transactions', 'embedding')
    op.add_column('transactions',
        sa.Column('embedding', sa.ARRAY(sa.Float()), nullable=True)
    )

    # projects
    op.execute('DROP INDEX IF EXISTS ix_projects_embedding')
    op.drop_column('projects', 'embedding')
    op.add_column('projects',
        sa.Column('embedding', sa.ARRAY(sa.Float()), nullable=True)
    )

    # tasks
    op.execute('DROP INDEX IF EXISTS ix_tasks_embedding')
    op.drop_column('tasks', 'embedding')
    op.add_column('tasks',
        sa.Column('embedding', sa.ARRAY(sa.Float()), nullable=True)
    )
