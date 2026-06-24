#!/usr/bin/env python3
"""
生成模块模板脚本

批量创建模块的基本文件结构
"""

import os
from typing import Dict, List

# 模块配置
MODULES = {
    "food": {
        "name": "美食推荐",
        "models": ["merchant"],
        "schemas": ["merchant"],
        "description": "包含美食搜索、商家信息、美食详情、评分等功能"
    },
    "attraction": {
        "name": "景点推荐",
        "models": ["attraction"],
        "schemas": ["attraction"],
        "description": "包含景点搜索、景点详情、景点评分等功能"
    },
    "chat": {
        "name": "智能助手",
        "models": ["chat"],
        "schemas": ["chat"],
        "description": "包含自然语言交互、意图识别、对话历史等功能"
    },
    "favorites": {
        "name": "收藏管理",
        "models": ["favorite"],
        "schemas": ["favorite"],
        "description": "包含用户收藏、收藏列表、收藏操作等功能"
    },
    "recommend": {
        "name": "今日推荐",
        "models": ["recommend"],
        "schemas": ["recommend"],
        "description": "包含个性化推荐、推荐反馈等功能"
    },
    "share": {
        "name": "分享功能",
        "models": ["share"],
        "schemas": ["share"],
        "description": "包含内容分享、分享记录等功能"
    },
    "xiaohongshu": {
        "name": "小红书集成",
        "models": ["xiaohongshu"],
        "schemas": ["xiaohongshu"],
        "description": "包含小红书笔记、内容缓存等功能"
    }
}

def create_init_file(module_path: str, module_name: str, description: str):
    """创建模块__init__.py文件"""
    content = f'''"""
{MODULES[module_name]["name"]}模块

{description}
"""

from .router import router as {module_name}_router

__all__ = ["{module_name}_router"]
'''
    with open(os.path.join(module_path, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_router_file(module_path: str, module_name: str):
    """创建模块router.py文件"""
    content = f'''"""
{MODULES[module_name]["name"]}模块路由

定义{MODULES[module_name]["name"]}相关的API端点
"""

from fastapi import APIRouter
from .controllers.{module_name}_controller import router as controller_router

# 创建模块路由
router = APIRouter()

# 包含控制器路由
router.include_router(controller_router, tags=["{MODULES[module_name]["name"]}"])

# 模块信息
MODULE_NAME = "{module_name}"
MODULE_PREFIX = "/{module_name}"
MODULE_TAGS = ["{MODULES[module_name]["name"]}"]
'''
    with open(os.path.join(module_path, "router.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_controller_init(module_path: str, module_name: str):
    """创建控制器__init__.py文件"""
    content = f'''"""
{MODULES[module_name]["name"]}模块控制器

处理HTTP请求和响应
"""

from .{module_name}_controller import router

__all__ = ["router"]
'''
    with open(os.path.join(module_path, "controllers", "__init__.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_controller_file(module_path: str, module_name: str):
    """创建控制器文件"""
    content = f'''"""
{MODULES[module_name]["name"]}控制器

处理{MODULES[module_name]["name"]}相关的HTTP请求
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from ..models.{MODULES[module_name]["models"][0]} import *
from ..schemas.{MODULES[module_name]["schemas"][0]}_schema import *
from ..services.{module_name}_service import {module_name.capitalize()}Service

router = APIRouter()


def get_{module_name}_service(db: Session = Depends(get_db)) -> {module_name.capitalize()}Service:
    """获取{MODULES[module_name]["name"]}服务实例"""
    return {module_name.capitalize()}Service(db)


# TODO: 添加具体的路由端点
'''
    with open(os.path.join(module_path, "controllers", f"{module_name}_controller.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_models_init(module_path: str, module_name: str):
    """创建模型__init__.py文件"""
    content = f'''"""
{MODULES[module_name]["name"]}模块模型

包含{MODULES[module_name]["name"]}相关的数据模型
"""

# TODO: 导入具体的模型
'''
    with open(os.path.join(module_path, "models", "__init__.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_schemas_init(module_path: str, module_name: str):
    """创建Schema __init__.py文件"""
    content = f'''"""
{MODULES[module_name]["name"]}模块Schema

包含{MODULES[module_name]["name"]}相关的Pydantic模型
"""

# TODO: 导入具体的Schema
'''
    with open(os.path.join(module_path, "schemas", "__init__.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_services_init(module_path: str, module_name: str):
    """创建服务__init__.py文件"""
    content = f'''"""
{MODULES[module_name]["name"]}模块服务

包含{MODULES[module_name]["name"]}相关的业务逻辑
"""

from .{module_name}_service import {module_name.capitalize()}Service

__all__ = ["{module_name.capitalize()}Service"]
'''
    with open(os.path.join(module_path, "services", "__init__.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_service_file(module_path: str, module_name: str):
    """创建服务文件"""
    content = f'''"""
{MODULES[module_name]["name"]}服务

处理{MODULES[module_name]["name"]}相关的业务逻辑
"""

from sqlalchemy.orm import Session
from typing import List, Optional

from ..models.{MODULES[module_name]["models"][0]} import *
from ..schemas.{MODULES[module_name]["schemas"][0]}_schema import *


class {module_name.capitalize()}Service:
    """{MODULES[module_name]["name"]}服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # TODO: 添加具体的业务方法
'''
    with open(os.path.join(module_path, "services", f"{module_name}_service.py"), "w", encoding="utf-8") as f:
        f.write(content)

def create_repositories_init(module_path: str, module_name: str):
    """创建repositories __init__.py文件"""
    content = f'''"""
{MODULES[module_name]["name"]}模块数据访问层

包含{MODULES[module_name]["name"]}相关的数据访问逻辑
"""

# TODO: 添加具体的数据访问类
'''
    with open(os.path.join(module_path, "repositories", "__init__.py"), "w", encoding="utf-8") as f:
        f.write(content)

def main():
    """主函数"""
    base_path = "d:/li/local_life_agent/backend/app/modules"
    
    for module_name, module_config in MODULES.items():
        module_path = os.path.join(base_path, module_name)
        
        print(f"创建模块: {module_name}")
        
        # 创建各个文件
        create_init_file(module_path, module_name, module_config["description"])
        create_router_file(module_path, module_name)
        create_controller_init(module_path, module_name)
        create_controller_file(module_path, module_name)
        create_models_init(module_path, module_name)
        create_schemas_init(module_path, module_name)
        create_services_init(module_path, module_name)
        create_service_file(module_path, module_name)
        create_repositories_init(module_path, module_name)
        
        print(f"模块 {module_name} 创建完成")

if __name__ == "__main__":
    main()