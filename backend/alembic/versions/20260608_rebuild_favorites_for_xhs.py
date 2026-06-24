"""重建 user_favorites 表以支持小红书笔记收藏

Revision ID: 20260608_rebuild
Revises: 20260608_add_xhs_notes
Create Date: 2026-06-08 16:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260608_rebuild_favorites'
down_revision = '20260608_add_xhs_notes'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 删除旧表
    op.drop_table('user_favorites')

    # 2. 创建新表
    op.create_table('user_favorites',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('note_id', sa.String(64), nullable=False, index=True),
        sa.Column('category', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['note_id'], ['xhs_notes.note_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('user_favorites')
    op.create_table('user_favorites',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('merchant_id', sa.BigInteger()),
        sa.Column('attraction_id', sa.BigInteger()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['attraction_id'], ['attractions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
