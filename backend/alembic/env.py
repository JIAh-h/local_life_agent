"""
Alembic环境配置文件

此文件在运行迁移命令时自动加载，配置数据库连接和迁移行为
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入数据库配置
from app.config import settings

# 导入所有模型（确保模型被注册到Base.metadata）
from app.database import Base
from app.models.user import User
from app.models.location import UserLocation, LocationLog
from app.models.merchant import Merchant, MerchantRating
from app.models.attraction import Attraction, AttractionRating
from app.models.xhs import XhsNote, XhsComment
from app.models.chat import ChatHistory, ChatContext, IntentLog
from app.models.favorite import UserFavorite
from app.models.share import ShareLog
from app.models.recommend import DailyRecommendation
from app.models.search import SearchHistory

# Alembic Config对象
config = context.config

# 设置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
target_metadata = Base.metadata


def get_url() -> str:
    """获取数据库连接URL"""
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """
    在'offline'模式下运行迁移
    
    这种模式下不需要数据库连接，只生成SQL脚本
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在'online'模式下运行迁移
    
    这种模式下需要数据库连接
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
