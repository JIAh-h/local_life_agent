"""
景点 API - 切换为小红书笔记数据源
原高德 POI 服务仅在定位模块使用
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.xiaohongshu_crawler import get_xhs_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/list")
async def get_attraction_list(
    keyword: str = Query(..., description="搜索关键词（来自定位模块的城市名）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
):
    """获取景点相关小红书笔记（取代旧版高德POI搜索）"""
    if not keyword.strip():
        raise HTTPException(status_code=400, detail="关键词不能为空")

    service = get_xhs_service()
    search_keyword = f"{keyword} 景点"
    logger.info(f"[景点] 搜索小红书笔记: '{search_keyword}'")
    notes = await service.search_notes(search_keyword, page, page_size)
    return {"notes": notes, "total": len(notes)}


@router.get("/{note_id}")
async def get_attraction_detail(note_id: str, xsec_token: str = Query(...)):
    """获取小红书笔记详情（取代旧版商家详情）"""
    if not note_id or not xsec_token:
        raise HTTPException(status_code=400, detail="参数不完整")

    service = get_xhs_service()
    detail = await service.get_note_detail(note_id, xsec_token)
    return detail
