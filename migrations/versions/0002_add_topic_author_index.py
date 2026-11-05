from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_topics_author", "topics", ["author"])


def downgrade():
    op.drop_index("ix_topics_author", table_name="topics")
