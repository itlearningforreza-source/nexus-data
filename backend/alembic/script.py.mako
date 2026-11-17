"""Alembic migration script template."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "${up_revision}"
down_revision = ${down_revision}
branch_labels = None
depends_on = None

def upgrade() -> None:
    ${upgrade_ops}

def downgrade() -> None:
    ${downgrade_ops}
