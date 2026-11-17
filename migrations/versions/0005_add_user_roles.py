from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column(
        "role", sa.String(8),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        nullable=False, server_default="user",
    ))


def downgrade():
    op.drop_column("users", "role")
