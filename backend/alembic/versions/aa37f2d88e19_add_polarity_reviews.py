"""add polarity reviews

Revision ID: aa37f2d88e19
Revises: 6975bfc83302
"""

from alembic import op
import sqlalchemy as sa

revision = "aa37f2d88e19"
down_revision = "6975bfc83302"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polarity_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cow_id", sa.String(length=50), nullable=False),
        sa.Column("section_key", sa.String(length=120), nullable=False),
        sa.Column("continuous_segment_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("first_source_file", sa.String(length=255), nullable=False),
        sa.Column("last_source_file", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cow_id", "section_key", name="uq_polarity_review_section"),
    )
    op.create_index("ix_polarity_reviews_cow_id", "polarity_reviews", ["cow_id"])
    op.create_index("ix_polarity_reviews_status", "polarity_reviews", ["status"])


def downgrade() -> None:
    op.drop_table("polarity_reviews")
