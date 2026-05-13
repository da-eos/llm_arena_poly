"""seed openrouter models

Revision ID: 18556e6a680a
Revises: 82fe3d86938a
Create Date: 2026-05-13 11:54:15.445960

"""
from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = '18556e6a680a'
down_revision: str | None = '82fe3d86938a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEED_MODELS = [
    ("openrouter-gpt-4o-mini",      "GPT-4o mini",       "openai/gpt-4o-mini"),
    ("openrouter-claude-haiku-3-5", "Claude 3.5 Haiku",  "anthropic/claude-3.5-haiku"),
    ("openrouter-gemini-flash-2-5", "Gemini 2.5 Flash",  "google/gemini-2.5-flash"),
    ("openrouter-llama-4-maverick", "Llama 4 Maverick",  "meta-llama/llama-4-maverick"),
    ("openrouter-deepseek-v3",      "DeepSeek V3",       "deepseek/deepseek-chat"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for slug, display_name, model_id in SEED_MODELS:
        conn.execute(
            sa.text(
                "INSERT INTO llm_models (id, slug, provider, display_name, "
                "model_id_at_provider, is_enabled, created_at) "
                "VALUES (:id, :slug, 'openrouter', :display_name, :model_id, true, now()) "
                "ON CONFLICT (slug) DO NOTHING"
            ).bindparams(
                id=uuid.uuid4(),
                slug=slug,
                display_name=display_name,
                model_id=model_id,
            )
        )


def downgrade() -> None:
    slugs = tuple(s for s, _, _ in SEED_MODELS)
    op.get_bind().execute(
        sa.text("DELETE FROM llm_models WHERE slug IN :slugs").bindparams(
            sa.bindparam("slugs", value=slugs, expanding=True)
        )
    )
