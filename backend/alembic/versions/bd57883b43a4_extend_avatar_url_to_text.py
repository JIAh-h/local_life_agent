"""extend_avatar_url_to_text

Revision ID: bd57883b43a4
Revises: 20260608_rebuild_favorites
Create Date: 2026-06-17 12:19:45.594889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'bd57883b43a4'
down_revision: Union[str, None] = '20260608_rebuild_favorites'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库结构"""
    op.alter_column('users', 'avatar_url',
               existing_type=mysql.VARCHAR(length=512),
               type_=sa.Text(),
               comment='头像URL或Base64',
               existing_nullable=True)


def downgrade() -> None:
    """降级数据库结构"""
    op.alter_column('users', 'avatar_url',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(length=512),
               comment='头像URL',
               existing_nullable=True)
