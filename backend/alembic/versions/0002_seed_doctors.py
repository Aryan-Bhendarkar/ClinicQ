"""seed starter doctors so the UI is usable on first run

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

doctors = sa.table("doctors", sa.column("name", sa.String), sa.column("specialty", sa.String))


def upgrade() -> None:
    op.bulk_insert(
        doctors,
        [
            {"name": "Dr. Asha Mehta", "specialty": "General Medicine"},
            {"name": "Dr. Rohan Iyer", "specialty": "Cardiology"},
            {"name": "Dr. Sana Khan", "specialty": "Pediatrics"},
            {"name": "Dr. Vikram Rao", "specialty": "Dermatology"},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM doctors WHERE name IN ('Dr. Asha Mehta','Dr. Rohan Iyer','Dr. Sana Khan','Dr. Vikram Rao')")
