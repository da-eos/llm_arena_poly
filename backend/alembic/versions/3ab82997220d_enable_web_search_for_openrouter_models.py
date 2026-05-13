"""enable web search for openrouter models

Revision ID: 3ab82997220d
Revises: 18556e6a680a
Create Date: 2026-05-13 12:46:47.996733

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ab82997220d'
down_revision: str | None = '18556e6a680a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Append ':online' to every openrouter model_id so OpenRouter routes the
    request through Exa web-search before answering. Idempotent: skips rows
    that already end in ':online'."""
    op.execute(
        sa.text(
            "UPDATE llm_models SET model_id_at_provider = model_id_at_provider || ':online' "
            "WHERE provider = 'openrouter' AND model_id_at_provider NOT LIKE '%:online'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE llm_models SET model_id_at_provider = "
            "regexp_replace(model_id_at_provider, ':online$', '') "
            "WHERE provider = 'openrouter' AND model_id_at_provider LIKE '%:online'"
        )
    )
