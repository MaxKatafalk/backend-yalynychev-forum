from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE topics ADD COLUMN owner_id INTEGER REFERENCES users(id)")
    op.execute("ALTER TABLE messages ADD COLUMN owner_id INTEGER REFERENCES users(id)")


def downgrade():
    op.execute("ALTER TABLE messages DROP COLUMN owner_id")
    op.execute("ALTER TABLE topics DROP COLUMN owner_id")
