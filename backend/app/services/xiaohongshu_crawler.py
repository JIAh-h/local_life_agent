"""
小红书爬虫服务 - 集成到小紫薯系统

封装了搜索笔记、获取笔记详情、获取评论三个核心功能。
headers/cookies 通过配置文件管理，支持热更新。
"""

import logging
import datetime
from typing import List, Optional, Dict, Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---- 默认请求头（通用字段，签名从 settings 加载）----
DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.xiaohongshu.com",
    "referer": "https://www.xiaohongshu.com/",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}

# ---- Cookies（硬编码，过期后从浏览器抓包更新）----
DEFAULT_COOKIES = {
    "abRequestId": "978685aa-7e13-5465-bf1c-58f1f0655503",
    "ets": "1780565707078",
    "webBuild": "6.14.5",
    "xsecappid": "xhs-pc-web",
    "loadts": "1780565707192",
    "webId": "3eca59eaae7ae691b7e9215e8f502690",
    "web_session": "0400698f6b992b566387b60e14384bbb2d79dc",
    "gid": "yjdjyiS0qjYSyjdjyiSYjJE2SqCAJj8E1x0yqKUYyqWT6A283i3q2x888yY22jJ88diifiKS",
    "x-rednote-datactry": "CN",
    "x-rednote-holderctry": "CN",
    "a1": "19e91fc89c3xq290wlha18137kmifi35823qhw56p50000185592",
    "id_token": "VjEAADeoZ9JUGySEcSalBsoNx2EVekvyZxtZIpc1KYG5l8lMKku7W8BIB+wsK5t3WYqqU72YQ9iLs2d2IxkeDDWQGgzG2tb8YCFFzJzJ/cs3S/roknE8cgby0UY7R+jMQ7usN804",
    "acw_tc": "0ad5960217806207206198669e1301e772f3d7f218fbd5668c4ab5b9acaebd",
    "websectiga": "59d3ef1e60c4aa37a7df3c23467bd46d7f1da0b1918cf335ee7f2e9e52ac04cf",
    "sec_poison_id": "19d7f7d2-64ea-4a00-aebc-50f7c89aad22",
}


def parse_timestamp(timestamp) -> str:
    """将小红书的毫秒时间戳转换为可读格式"""
    if not timestamp:
        return ""
    try:
        ts = int(timestamp)
        if len(str(ts)) == 13:
            ts = ts / 1000
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return str(timestamp)


# ===== 结构化日志辅助 =====

def _log_xhs(
    action: str,
    status: str,
    *,
    keyword: str = "",
    note_id: str = "",
    cursor: str = "",
    count: int = -1,
    total: int = -1,
    has_more: bool = False,
    images: int = -1,
    comments_cnt: int = -1,
    http_code: int = 0,
    api_msg: str = "",
    error: str = "",
    detail: str = "",
):
    """
    结构化小红书日志，方便 grep 和问题定位。

    action: SEARCH / DETAIL / COMMENT / IMAGE_PROXY / PARSE
    status: SUCCESS / EMPTY / FAILED / PARTIAL / WARN
    """
    parts = [f"[XHS] [{action}] [{status}]"]
    if keyword:
        parts.append(f"keyword={keyword}")
    if note_id:
        parts.append(f"note_id={note_id[:12]}")  # 截断避免过长
    if cursor:
        parts.append(f"cursor={cursor[:8]}")
    if count >= 0:
        parts.append(f"count={count}")
    if total >= 0:
        parts.append(f"total={total}")
    if has_more:
        parts.append("has_more=true")
    if images >= 0:
        parts.append(f"images={images}")
    if comments_cnt >= 0:
        parts.append(f"comments={comments_cnt}")
    if http_code:
        parts.append(f"http={http_code}")
    if api_msg:
        parts.append(f"api_msg={api_msg}")
    if error:
        parts.append(f"error={error}")
    if detail:
        parts.append(f"detail={detail}")

    log_line = " | ".join(parts)

    if status == "FAILED":
        logger.error(log_line)
    elif status == "WARN":
        logger.warning(log_line)
    else:
        logger.info(log_line)


class XiaohongshuService:
    """小红书爬虫服务"""

    SEARCH_URL = "https://so.xiaohongshu.com/api/sns/web/v2/search/notes"
    FEED_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/feed"
    COMMENT_URL = "https://edith.xiaohongshu.com/api/sns/web/v2/comment/page"

    def __init__(self):
        self._cookies = dict(DEFAULT_COOKIES)

        # 构造各接口独立 x-s 签名
        x_s_common = getattr(settings, "XHS_X_S_COMMON", "") or ""

        self._headers_search = dict(DEFAULT_HEADERS)
        self._headers_search["x-s"] = (getattr(settings, "XHS_X_S_SEARCH", "") or "")
        self._headers_search["x-s-common"] = x_s_common

        self._headers_feed = dict(DEFAULT_HEADERS)
        self._headers_feed["x-s"] = (getattr(settings, "XHS_X_S_FEED", "") or "")
        self._headers_feed["x-s-common"] = x_s_common

        self._headers_comment = dict(DEFAULT_HEADERS)
        self._headers_comment["x-s"] = (getattr(settings, "XHS_X_S_COMMENT", "") or "")
        self._headers_comment["x-s-common"] = x_s_common

        # 记录签名加载状态
        for name, h in [("SEARCH", self._headers_search), ("FEED", self._headers_feed), ("COMMENT", self._headers_comment)]:
            has_sig = bool(h.get("x-s")) and bool(h.get("x-s-common"))
            if not has_sig:
                _log_xhs("INIT", "WARN", note_id=name, detail=f"{name} x-s 未配置或为空")

    @staticmethod
    def _parse_count(val) -> int:
        """将小红书 API 返回的互动数值（可能为 int 或 "1.6万" 格式）转为整数"""
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return 0
            if "万" in val:
                try:
                    num = float(val.replace("万", ""))
                    return int(num * 10000)
                except (ValueError, TypeError):
                    return 0
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0
        return 0

    # ---- 公开方法 ----

    async def search_notes(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Dict]:
        """
        根据关键词搜索笔记

        Returns:
            [{ id, xsec_token, display_title, cover_url, publish_time, thumbnails, user }]
        """
        json_data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "sort": "general",
            "note_type": 0,
            "ext_flags": [],
            "geo": "",
            "image_formats": ["jpg", "webp", "avif"],
            "message_id": "sending",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self.SEARCH_URL,
                    cookies=self._cookies,
                    headers=self._headers_search,
                    json=json_data,
                )
                data = resp.json()
                http_code = resp.status_code

                if http_code == 406:
                    # 406 Not Acceptable — 通常是签名无效
                    _log_xhs("SEARCH", "FAILED", keyword=keyword, http_code=406,
                             detail=f"响应体: {str(data)[:200]}")
                    return []

                if data.get("success"):
                    _log_xhs(
                        "SEARCH", "SUCCESS",
                        keyword=keyword, count=len(data.get("data", {}).get("items", [])),
                        http_code=http_code,
                    )
                else:
                    api_msg = data.get("msg", data.get("info", "未知错误"))
                    _log_xhs(
                        "SEARCH", "FAILED",
                        keyword=keyword, http_code=http_code, api_msg=api_msg,
                    )
                    return []
        except httpx.TimeoutException:
            _log_xhs("SEARCH", "FAILED", keyword=keyword, error="timeout(15s)")
            return []
        except Exception as e:
            _log_xhs("SEARCH", "FAILED", keyword=keyword, error=str(e))
            return []

        return self._parse_search_results(data, keyword)

    async def get_note_detail(self, note_id: str, xsec_token: str) -> Dict:
        """
        获取笔记详情（描述 + 图片列表 + 用户信息）

        Returns:
            { desc, image_urls, display_title, liked_count, ... }
        """
        json_data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": "1"},
            "xsec_token": xsec_token,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self.FEED_URL,
                    cookies=self._cookies,
                    headers=self._headers_feed,
                    json=json_data,
                )
                data = resp.json()
                http_code = resp.status_code

                if http_code == 406:
                    _log_xhs("DETAIL", "FAILED", note_id=note_id, http_code=406,
                             detail=f"签名无效或已过期, 响应体: {str(data)[:200]}")
                    return {"desc": "", "image_urls": []}

                if data.get("success"):
                    items = data.get("data", {}).get("items", [])
                    _log_xhs(
                        "DETAIL", "SUCCESS",
                        note_id=note_id, count=len(items), http_code=http_code,
                    )
                else:
                    api_msg = data.get("msg", data.get("info", "未知错误"))
                    _log_xhs(
                        "DETAIL", "FAILED",
                        note_id=note_id, http_code=http_code, api_msg=api_msg,
                    )
                    return {"desc": "", "image_urls": []}
        except httpx.TimeoutException:
            _log_xhs("DETAIL", "FAILED", note_id=note_id, error="timeout(15s)")
            return {"desc": "", "image_urls": []}
        except Exception as e:
            _log_xhs("DETAIL", "FAILED", note_id=note_id, error=str(e))
            return {"desc": "", "image_urls": []}

        return self._parse_note_detail(data, note_id)

    async def get_comments(self, note_id: str, xsec_token: str, cursor: str = "") -> Dict:
        """
        获取笔记评论

        Returns:
            { comments: [...], cursor: str, has_more: bool }
        """
        url = (
            f"{self.COMMENT_URL}"
            f"?note_id={note_id}&cursor={cursor}&top_comment_id="
            f"&image_formats=jpg,webp,avif&xsec_token={xsec_token}"
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, cookies=self._cookies, headers=self._headers_comment)
                data = resp.json()
                http_code = resp.status_code

                if http_code == 406:
                    _log_xhs("COMMENT", "FAILED", note_id=note_id, cursor=cursor, http_code=406,
                             detail=f"签名无效或已过期, 响应体: {str(data)[:200]}")
                    return {"comments": [], "cursor": "", "has_more": False}

                if data.get("success"):
                    comment_list = data.get("data", {}).get("comments", [])
                    _log_xhs(
                        "COMMENT", "SUCCESS",
                        note_id=note_id, cursor=cursor, comments_cnt=len(comment_list),
                        http_code=http_code,
                    )
                else:
                    api_msg = data.get("msg", data.get("info", "未知错误"))
                    _log_xhs(
                        "COMMENT", "FAILED",
                        note_id=note_id, cursor=cursor, http_code=http_code, api_msg=api_msg,
                    )
                    return {"comments": [], "cursor": "", "has_more": False}
        except httpx.TimeoutException:
            _log_xhs("COMMENT", "FAILED", note_id=note_id, cursor=cursor, error="timeout(15s)")
            return {"comments": [], "cursor": "", "has_more": False}
        except Exception as e:
            _log_xhs("COMMENT", "FAILED", note_id=note_id, cursor=cursor, error=str(e))
            return {"comments": [], "cursor": "", "has_more": False}

        return self._parse_comments(data, note_id)

    # ---- 内部解析方法 ----

    def _parse_search_results(self, response_data: dict, keyword: str = "") -> List[Dict]:
        results = []
        if not response_data.get("success") or "data" not in response_data:
            _log_xhs("PARSE", "FAILED", keyword=keyword, detail="响应缺少 data 字段")
            return results

        items = response_data["data"].get("items", [])
        _log_xhs("PARSE", "INFO", keyword=keyword, detail=f"原始 items={len(items)}")

        for item in items:
            if item.get("model_type") != "note":
                continue

            note_id = item.get("id")
            xsec_token = item.get("xsec_token")
            note_card = item.get("note_card", {})
            cover = note_card.get("cover", {})
            corner_tag_info = note_card.get("corner_tag_info", [])

            publish_time = ""
            if corner_tag_info and len(corner_tag_info) > 0:
                publish_time = corner_tag_info[0].get("text", "")

            # 提取缩略图
            image_list = note_card.get("image_list", [])
            thumbnails = []
            for img in image_list[:3]:
                url_default = img.get("url_default", "")
                if url_default:
                    thumbnails.append(url_default)

            results.append({
                "id": note_id,
                "xsec_token": xsec_token,
                "display_title": note_card.get("display_title", ""),
                "cover_url": cover.get("url_default", ""),
                "publish_time": publish_time,
                "thumbnails": thumbnails,
                "user": {
                    "nickname": note_card.get("user", {}).get("nickname", ""),
                    "avatar": note_card.get("user", {}).get("avatar", ""),
                },
            })

        if results:
            _log_xhs(
                "PARSE", "SUCCESS", keyword=keyword, count=len(results),
                detail=f"有效笔记={len(results)}, 过滤非笔记={len(items)-len(results)}",
            )
        else:
            _log_xhs(
                "PARSE", "EMPTY", keyword=keyword, total=len(items),
                detail="解析后无有效笔记",
            )

        return results

    def _parse_note_detail(self, response_data: dict, note_id: str = "") -> Dict:
        result = {
            "desc": "", "image_urls": [], "display_title": "",
            "liked_count": 0, "collected_count": 0, "comment_count": 0,
            "user": {}, "publish_time": "",
        }

        if not response_data.get("success") or "data" not in response_data:
            _log_xhs("PARSE", "FAILED", note_id=note_id, detail="响应缺少 data 字段")
            return result

        items = response_data["data"].get("items", [])
        if not items:
            _log_xhs("PARSE", "EMPTY", note_id=note_id, detail="items 为空列表")
            return result

        note_card = items[0].get("note_card", {})

        result["desc"] = note_card.get("desc", "")
        result["display_title"] = note_card.get("display_title", "")

        # 用户信息
        user = note_card.get("user", {})
        result["user"] = {
            "nickname": user.get("nickname", ""),
            "avatar": user.get("avatar", ""),
        }

        # 互动数据（小红书可能返回格式化字符串如 "1.6万"）
        interact = note_card.get("interact_info", {})
        result["liked_count"] = self._parse_count(interact.get("liked_count", 0))
        result["collected_count"] = self._parse_count(interact.get("collected_count", 0))
        result["comment_count"] = self._parse_count(interact.get("comment_count", 0))

        # 发布时间（小红书可能返回字符串或毫秒时间戳）
        time_val = note_card.get("time", "")
        if isinstance(time_val, (int, float)):
            time_val = str(int(time_val))
        elif not time_val:
            time_val = note_card.get("publish_time", "")
        result["publish_time"] = time_val

        # 图片列表
        image_list = note_card.get("image_list", [])
        for img in image_list:
            url_default = img.get("url_default", "")
            if url_default:
                result["image_urls"].append(url_default)

        # 数据可用性摘要
        has_title = bool(result["display_title"])
        has_desc = bool(result["desc"])
        has_user = bool(result["user"]["nickname"])
        images_count = len(result["image_urls"])

        detail_parts = [
            f"title={'Y' if has_title else 'N'}",
            f"desc={'Y' if has_desc else 'N'}",
            f"user={'Y' if has_user else 'N'}",
            f"images={images_count}",
            f"likes={result['liked_count']}",
        ]

        if images_count > 0:
            _log_xhs(
                "PARSE", "SUCCESS", note_id=note_id, count=len(items),
                images=images_count, detail=", ".join(detail_parts),
            )
        else:
            _log_xhs(
                "PARSE", "EMPTY", note_id=note_id, count=len(items),
                images=0, detail=", ".join(detail_parts) + " | note_card 无图片列表",
            )

        return result

    def _parse_comments(self, response_data: dict, note_id: str = "") -> Dict:
        comments = []
        cursor = response_data.get("data", {}).get("cursor", "")
        has_more = response_data.get("data", {}).get("has_more", False)

        if not response_data.get("success") or "data" not in response_data:
            _log_xhs("PARSE", "FAILED", note_id=note_id, detail="响应缺少 data 字段")
            return {"comments": [], "cursor": cursor, "has_more": has_more}

        comment_list = response_data["data"].get("comments", [])
        if not comment_list:
            _log_xhs("PARSE", "EMPTY", note_id=note_id, detail="comments 为空列表", has_more=has_more)
            return {"comments": [], "cursor": cursor, "has_more": has_more}

        for item in comment_list:
            user_info = item.get("user_info", {})
            main_comment = {
                "id": item.get("id", ""),
                "content": item.get("content", ""),
                "create_time": parse_timestamp(item.get("create_time", "")),
                "ip_location": item.get("ip_location", ""),
                "like_count": item.get("like_count", 0),
                "user_nickname": user_info.get("nickname", ""),
                "user_image": user_info.get("image", ""),
            }

            sub_comments = []
            for sub in item.get("sub_comments", []):
                sub_user_info = sub.get("user_info", {})
                sub_comments.append({
                    "id": sub.get("id", ""),
                    "content": sub.get("content", ""),
                    "create_time": parse_timestamp(sub.get("create_time", "")),
                    "ip_location": sub.get("ip_location", ""),
                    "user_nickname": sub_user_info.get("nickname", ""),
                    "user_image": sub_user_info.get("image", ""),
                })

            main_comment["sub_comments"] = sub_comments
            comments.append(main_comment)

        sub_total = sum(len(c.get("sub_comments", [])) for c in comments)
        _log_xhs(
            "PARSE", "SUCCESS", note_id=note_id, comments_cnt=len(comments),
            has_more=has_more,
            detail=f"主评论={len(comments)}, 子评论={sub_total}",
        )

        return {"comments": comments, "cursor": cursor, "has_more": has_more}


# ---- 全局单例 ----
_xhs_service: Optional[XiaohongshuService] = None


def get_xhs_service() -> XiaohongshuService:
    global _xhs_service
    if _xhs_service is None:
        _xhs_service = XiaohongshuService()
    return _xhs_service
