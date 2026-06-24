"""
小红书 API 路由 - 为前端提供笔记搜索、详情、评论接口
"""
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

from app.services.xiaohongshu_crawler import get_xhs_service

logger = logging.getLogger(__name__)
router = APIRouter()


class SearchRequest(BaseModel):
    keyword: str
    page: int = 1
    page_size: int = 20


class NoteDetailRequest(BaseModel):
    note_id: str
    xsec_token: str


class CommentRequest(BaseModel):
    note_id: str
    xsec_token: str
    cursor: str = ""


def _log_api(action: str, status: str, **kwargs):
    """结构化 API 层日志，格式与 service 层一致"""
    parts = [f"[XHS] [{action}] [{status}]"]
    for k, v in kwargs.items():
        if v is not None and v != "":
            parts.append(f"{k}={v}")
    log_line = " | ".join(parts)
    if status == "FAILED":
        logger.error(log_line)
    elif status == "WARN":
        logger.warning(log_line)
    else:
        logger.info(log_line)


@router.post("/search", summary="小红书笔记搜索")
async def search_notes(req: SearchRequest):
    """根据关键词搜索小红书笔记"""
    if not req.keyword.strip():
        _log_api("SEARCH", "FAILED", keyword=req.keyword, detail="关键词为空")
        raise HTTPException(status_code=400, detail="关键词不能为空")

    service = get_xhs_service()
    notes = await service.search_notes(req.keyword, req.page, req.page_size)

    has_data = len(notes) > 0
    status = "SUCCESS" if has_data else "EMPTY"
    _log_api(
        "SEARCH", status,
        keyword=req.keyword, count=len(notes),
        detail=f"前端收到 {len(notes)} 条笔记",
    )

    return {"notes": notes, "total": len(notes)}


@router.post("/note/detail", summary="获取笔记详情")
async def get_note_detail(req: NoteDetailRequest):
    """获取笔记的完整描述和图片列表"""
    if not req.note_id or not req.xsec_token:
        _log_api("DETAIL", "FAILED", detail="参数不完整")
        raise HTTPException(status_code=400, detail="参数不完整")

    service = get_xhs_service()
    detail = await service.get_note_detail(req.note_id, req.xsec_token)

    # 数据可用性判断
    has_title = bool(detail.get("display_title"))
    has_desc = bool(detail.get("desc"))
    images_count = len(detail.get("image_urls", []))
    has_user = bool(detail.get("user", {}).get("nickname"))

    if images_count == 0 and not has_title and not has_desc:
        status = "EMPTY"
    elif images_count > 0 or has_desc:
        status = "SUCCESS"
    else:
        status = "PARTIAL"

    _log_api(
        "DETAIL", status,
        note_id=req.note_id,
        images=images_count,
        detail=f"title={'Y' if has_title else 'N'} desc={'Y' if has_desc else 'N'} user={'Y' if has_user else 'N'}",
    )

    return detail


@router.post("/note/comments", summary="获取笔记评论")
async def get_note_comments(req: CommentRequest):
    """获取笔记的评论列表"""
    if not req.note_id or not req.xsec_token:
        _log_api("COMMENT", "FAILED", detail="参数不完整")
        raise HTTPException(status_code=400, detail="参数不完整")

    service = get_xhs_service()
    result = await service.get_comments(req.note_id, req.xsec_token, req.cursor)

    comments = result.get("comments", [])
    status = "SUCCESS" if len(comments) > 0 else "EMPTY"

    _log_api(
        "COMMENT", status,
        note_id=req.note_id, comments=len(comments),
        has_more=result.get("has_more", False),
        detail=f"cursor={req.cursor or '首页'}",
    )

    return result


@router.get("/image-proxy", summary="小红书图片代理")
async def image_proxy(url: str = Query(..., description="小红书图片URL")):
    """
    代理加载小红书图片绕过CDN防盗链。
    前端将 xhs CDN 图片 URL 传给此接口，后端携带正确的 Referer 加载后流式返回。
    """
    if not url.startswith("http"):
        _log_api("IMAGE_PROXY", "FAILED", detail=f"无效URL: {url[:60]}")
        raise HTTPException(status_code=400, detail="无效的图片URL")

    service = get_xhs_service()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                url,
                headers={
                    "Referer": "https://www.xiaohongshu.com/",
                    "User-Agent": service._headers_search.get("User-Agent", ""),
                },
                cookies=service._cookies,
                follow_redirects=True,
            )
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "image/jpeg")
            content_len = resp.headers.get("content-length", "?")
            _log_api(
                "IMAGE_PROXY", "SUCCESS",
                detail=f"loaded size={content_len}B type={content_type}",
            )

            return StreamingResponse(
                resp.iter_bytes(),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except httpx.TimeoutException:
        _log_api("IMAGE_PROXY", "FAILED", detail=f"timeout(20s) url={url[:60]}")
        raise HTTPException(status_code=502, detail="图片加载超时")
    except httpx.HTTPStatusError as e:
        _log_api("IMAGE_PROXY", "FAILED", detail=f"http={e.response.status_code} url={url[:60]}")
        raise HTTPException(status_code=502, detail="图片加载失败")
    except Exception as e:
        _log_api("IMAGE_PROXY", "FAILED", detail=f"{str(e)[:80]} url={url[:60]}")
        raise HTTPException(status_code=502, detail="图片加载失败")
