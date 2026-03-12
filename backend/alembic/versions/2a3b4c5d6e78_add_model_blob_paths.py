"""add model blob paths to assessments

Revision ID: 2a3b4c5d6e78
Revises: 1f84f56caa94
Create Date: 2026-03-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a3b4c5d6e78"
down_revision: Union[str, None] = "1f84f56caa94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("exterior_model_blob_path", sa.Text(), nullable=True))
    op.add_column("assessments", sa.Column("interior_model_blob_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessments", "interior_model_blob_path")
    op.drop_column("assessments", "exterior_model_blob_path")

