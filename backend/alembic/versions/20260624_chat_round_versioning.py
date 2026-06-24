"""为 chat_history 表添加轮次版本管理字段

支持重新生成（regenerate）功能的持久化：
- round_id: 标识同一轮问答的 ID，用户的提问与多次 AI 回复共享同一个 round_id
- is_latest: 标记是否为该轮次的最新版本
- version: 版本号，从 1 开始递增

Revision ID: 20260624_chat_round_versioning
Revises: bd57883b43a4
Create Date: 2026-06-24 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20260624_chat_round_versioning'
down_revision = 'bd57883b43a4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 添加新字段
    op.add_column('chat_history', sa.Column(
        'round_id', sa.String(64), nullable=True, comment='轮次ID，同一轮问答共享'
    ))
    op.add_column('chat_history', sa.Column(
        'is_latest', sa.Boolean(), server_default=sa.text('1'), comment='是否为最新版本'
    ))
    op.add_column('chat_history', sa.Column(
        'version', sa.Integer(), server_default=sa.text('1'), comment='版本号，从1开始'
    ))

    # 2. 为已有记录回填默认值
    op.execute(
        "UPDATE chat_history "
        "SET round_id = CONCAT(session_id, '_', id), "
        "    is_latest = 1, "
        "    version = 1 "
        "WHERE round_id IS NULL"
    )

    # 3. 将 round_id 改为 NOT NULL
    op.alter_column('chat_history', 'round_id',
                    existing_type=sa.String(64),
                    nullable=False,
                    comment='轮次ID，同一轮问答共享')

    # 4. 创建索引
    op.create_index('idx_chat_round_id', 'chat_history', ['round_id'])
    op.create_index('idx_chat_latest', 'chat_history',
                    ['user_id', 'session_id', 'is_latest'])


def downgrade() -> None:
    # 1. 删除索引
    op.drop_index('idx_chat_latest', table_name='chat_history')
    op.drop_index('idx_chat_round_id', table_name='chat_history')

    # 2. 删除字段
    op.drop_column('chat_history', 'version')
    op.drop_column('chat_history', 'is_latest')
    op.drop_column('chat_history', 'round_id')
