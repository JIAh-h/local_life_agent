"""新增小红书笔记和评论表

Revision ID: 20260608_add_xhs_notes
Revises: bb356f4dbc0e
Create Date: 2026-06-08 11:23:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision: str = '20260608_add_xhs_notes'
down_revision: Union[str, None] = 'bb356f4dbc0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 删除旧表（xiaohongshu_notes / note_cache 不再使用）
    op.drop_table('note_cache')
    op.drop_table('xiaohongshu_notes')

    # 2. 创建新表 - 小红书笔记表
    op.create_table('xhs_notes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('note_id', sa.String(length=64), nullable=False, comment='小红书笔记ID'),
        sa.Column('xsec_token', sa.String(length=256), nullable=False, comment='访问令牌'),
        sa.Column('display_title', sa.String(length=256), nullable=True, comment='标题'),
        sa.Column('cover_url', sa.Text(), nullable=True, comment='封面图URL'),
        sa.Column('publish_time', sa.String(length=32), nullable=True, comment='发布时间'),
        sa.Column('author_name', sa.String(length=64), nullable=True, comment='作者昵称'),
        sa.Column('author_avatar', sa.Text(), nullable=True, comment='作者头像'),
        sa.Column('thumbnails', sa.JSON(), nullable=True, comment='缩略图列表'),
        sa.Column('image_urls', sa.JSON(), nullable=True, comment='完整图片列表'),
        sa.Column('description', sa.Text(), nullable=True, comment='完整文案'),
        sa.Column('like_count', sa.Integer(), default=0, nullable=True, comment='点赞数'),
        sa.Column('collect_count', sa.Integer(), default=0, nullable=True, comment='收藏数'),
        sa.Column('search_keyword', sa.String(length=128), nullable=True, comment='搜索关键词'),
        sa.Column('source', sa.String(length=32), default='xiaohongshu', nullable=True, comment='数据来源'),
        sa.Column('status', sa.SmallInteger(), default=1, nullable=True, comment='状态 0删除 1正常'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('note_id'),
    )
    op.create_index('idx_note_id', 'xhs_notes', ['note_id'])
    op.create_index('idx_search_keyword', 'xhs_notes', ['search_keyword'])
    op.create_index('idx_created_at', 'xhs_notes', ['created_at'])

    # 3. 创建新表 - 小红书评论表
    op.create_table('xhs_comments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('comment_id', sa.String(length=64), nullable=False, comment='小红书评论ID'),
        sa.Column('note_id', sa.String(length=64), nullable=False, comment='所属笔记ID'),
        sa.Column('parent_id', sa.String(length=64), nullable=True, comment='父评论ID（NULL=主评论）'),
        sa.Column('content', sa.Text(), nullable=False, comment='评论内容'),
        sa.Column('create_time', sa.String(length=32), nullable=True, comment='评论时间'),
        sa.Column('ip_location', sa.String(length=64), nullable=True, comment='IP属地'),
        sa.Column('like_count', sa.Integer(), default=0, nullable=True, comment='点赞数'),
        sa.Column('user_nickname', sa.String(length=64), nullable=True, comment='用户昵称'),
        sa.Column('user_avatar', sa.Text(), nullable=True, comment='用户头像'),
        sa.Column('status', sa.SmallInteger(), default=1, nullable=True, comment='状态'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id'),
        sa.ForeignKeyConstraint(['note_id'], ['xhs_notes.note_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_comment_note_id', 'xhs_comments', ['note_id'])
    op.create_index('idx_comment_parent_id', 'xhs_comments', ['parent_id'])


def downgrade() -> None:
    # 回滚：删除新表，恢复旧表
    op.drop_table('xhs_comments')
    op.drop_table('xhs_notes')

    # 恢复旧表 xiaohongshu_notes
    op.create_table('xiaohongshu_notes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('merchant_id', sa.BigInteger(), nullable=True, comment='关联商家ID'),
        sa.Column('attraction_id', sa.BigInteger(), nullable=True, comment='关联景点ID'),
        sa.Column('title', sa.String(length=256), nullable=False, comment='笔记标题'),
        sa.Column('author', sa.String(length=64), nullable=False, comment='作者昵称'),
        sa.Column('author_avatar', sa.String(length=512), nullable=True, comment='作者头像'),
        sa.Column('publish_time', sa.DateTime(), nullable=False, comment='发布时间'),
        sa.Column('like_count', sa.Integer(), nullable=True, comment='点赞数'),
        sa.Column('comment_count', sa.Integer(), nullable=True, comment='评论数'),
        sa.Column('collect_count', sa.Integer(), nullable=True, comment='收藏数'),
        sa.Column('content', sa.Text(), nullable=True, comment='笔记内容'),
        sa.Column('summary', sa.Text(), nullable=True, comment='内容摘要'),
        sa.Column('pros', sa.JSON(), nullable=True, comment='优点列表'),
        sa.Column('cons', sa.JSON(), nullable=True, comment='缺点列表'),
        sa.Column('tips', sa.JSON(), nullable=True, comment='避坑提示'),
        sa.Column('original_url', sa.String(length=512), nullable=False, comment='原文链接'),
        sa.Column('images', sa.JSON(), nullable=True, comment='笔记图片'),
        sa.Column('source', sa.String(length=32), nullable=True, comment='数据来源'),
        sa.Column('source_id', sa.String(length=64), nullable=True, comment='来源ID'),
        sa.Column('status', sa.SmallInteger(), nullable=True, comment='状态（0禁用 1正常）'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['attraction_id'], ['attractions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 恢复旧表 note_cache
    op.create_table('note_cache',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('cache_key', sa.String(length=256), nullable=False, comment='缓存键'),
        sa.Column('cache_value', sa.Text(), nullable=False, comment='缓存值'),
        sa.Column('expire_time', sa.DateTime(), nullable=False, comment='过期时间'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cache_key'),
    )
