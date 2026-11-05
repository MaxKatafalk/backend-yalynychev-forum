from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("status", sa.String(6), nullable=False, server_default="open"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_topics_status"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade():
    op.drop_table("messages")
    op.drop_table("topics")
