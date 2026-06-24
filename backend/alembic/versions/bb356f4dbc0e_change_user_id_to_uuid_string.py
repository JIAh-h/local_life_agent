"""change_user_id_to_uuid_string

Revision ID: bb356f4dbc0e
Revises: 20260602_add_user_auth_fields
Create Date: 2026-06-03 17:33:52.852509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'bb356f4dbc0e'
down_revision: Union[str, None] = '20260602_add_user_auth_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库结构"""
    # ### 修复：MySQL 必须先删除外键约束，然后才能修改列类型 ###
    # 1. 先删除所有外键约束
    op.drop_constraint('chat_context_ibfk_1', 'chat_context', type_='foreignkey')
    op.drop_constraint('chat_history_ibfk_1', 'chat_history', type_='foreignkey')
    op.drop_constraint('intent_logs_ibfk_1', 'intent_logs', type_='foreignkey')
    # 2. 再修改列类型从 BIGINT 到 String(36)
    op.alter_column('chat_context', 'user_id',
               existing_type=mysql.BIGINT(),
               type_=sa.String(length=36),
               comment='用户ID（支持UUID格式）',
               existing_comment='用户ID',
               existing_nullable=False)
    op.alter_column('chat_history', 'user_id',
               existing_type=mysql.BIGINT(),
               type_=sa.String(length=36),
               comment='用户ID（支持UUID格式）',
               existing_comment='用户ID',
               existing_nullable=False)
    op.alter_column('intent_logs', 'user_id',
               existing_type=mysql.BIGINT(),
               type_=sa.String(length=36),
               comment='用户ID（支持UUID格式）',
               existing_comment='用户ID',
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """降级数据库结构"""
    # ### 修复：先修改列类型，然后才能重新创建外键约束 ###
    # 1. 先修改列类型从 String(36) 回到 BIGINT
    op.alter_column('intent_logs', 'user_id',
               existing_type=sa.String(length=36),
               type_=mysql.BIGINT(),
               comment='用户ID',
               existing_comment='用户ID（支持UUID格式）',
               existing_nullable=False)
    op.alter_column('chat_history', 'user_id',
               existing_type=sa.String(length=36),
               type_=mysql.BIGINT(),
               comment='用户ID',
               existing_comment='用户ID（支持UUID格式）',
               existing_nullable=False)
    op.alter_column('chat_context', 'user_id',
               existing_type=sa.String(length=36),
               type_=mysql.BIGINT(),
               comment='用户ID',
               existing_comment='用户ID（支持UUID格式）',
               existing_nullable=False)
    # 2. 再重新创建外键约束
    op.create_foreign_key('intent_logs_ibfk_1', 'intent_logs', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('chat_history_ibfk_1', 'chat_history', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('chat_context_ibfk_1', 'chat_context', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###
