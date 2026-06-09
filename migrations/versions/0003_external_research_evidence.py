"""add external research evidence fields

Revision ID: 0003_external_research_evidence
Revises: 0002_opportunity_engine
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_external_research_evidence"
down_revision = "0002_opportunity_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("source_type", sa.String(), nullable=False, server_default="inferred"))
    op.add_column("opportunities", sa.Column("evidence_summary", sa.Text(), nullable=True))
    op.add_column("opportunities", sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("opportunities", sa.Column("evidence_items_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunities", "evidence_items_json")
    op.drop_column("opportunities", "needs_verification")
    op.drop_column("opportunities", "evidence_summary")
    op.drop_column("opportunities", "source_type")
