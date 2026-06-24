import json
import httpx
import re
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.models.xiaohongshu import XhsNote
from app.schemas.xiaohongshu import NoteListResponse
from app.redis_client import get_redis
from app.config import settings

logger = logging.getLogger(__name__)

# NLP关键词库：用于提取评价信息
PROS_KEYWORDS = [
    "好吃", "美味", "推荐", "不错", "赞", "好评", "值得", "满意", "棒", "好",
    "新鲜", "实惠", "服务好", "环境好", "干净", "卫生", "地道", "正宗", "特色",
    "必吃", "必去", "打卡", "推荐", "惊艳", "惊喜", "超出预期"
]

CONS_KEYWORDS = [
    "难吃", "踩雷", "失望", "差评", "不好", "贵", "性价比低", "排队", "等很久",
    "服务差", "态度差", "不卫生", "不新鲜", "一般", "普通", "不推荐", "坑",
    "踩坑", "翻车", "后悔", "再也不来"
]

TIPS_KEYWORDS = [
    "注意", "提醒", "避坑", "建议", "提前", "预约", "预约", "高峰期", "避开",
    "最好", "不要", "千万别", "记得", "别忘", "小心", "攻略", "tips", "tip"
]


class XhsService:
    """小红书服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
    
    def search_notes(
        self,
        merchant_id: Optional[int] = None,
        attraction_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> NoteListResponse:
        """搜索小红书笔记"""
        query = self.db.query(XhsNote).filter(XhsNote.status == 1)
        
        # 按关联ID筛选
        if merchant_id:
            query = query.filter(XhsNote.merchant_id == merchant_id)
        if attraction_id:
            query = query.filter(XhsNote.attraction_id == attraction_id)
        
        # 如果没有本地数据，尝试调用API获取
        if query.count() == 0:
            keyword = ""
            if merchant_id:
                merchant = self.db.query(XhsNote).filter(XhsNote.merchant_id == merchant_id).first()
                # 从merchant表获取名称
                from app.models.merchant import Merchant
                m = self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
                if m:
                    keyword = m.name
            elif attraction_id:
                from app.models.attraction import Attraction
                a = self.db.query(Attraction).filter(Attraction.id == attraction_id).first()
                if a:
                    keyword = a.name
            
            if keyword:
                api_results = self._call_xhs_api(keyword, sort_by)
                if api_results:
                    self._save_notes_to_db(api_results, merchant_id, attraction_id)
        
        # 重新构建查询
        query = self.db.query(XhsNote).filter(XhsNote.status == 1)
        if merchant_id:
            query = query.filter(XhsNote.merchant_id == merchant_id)
        if attraction_id:
            query = query.filter(XhsNote.attraction_id == attraction_id)
        
        # 排序
        if sort_by == "like":
            query = query.order_by(XhsNote.like_count.desc())
        elif sort_by == "comment":
            query = query.order_by(XhsNote.comment_count.desc())
        elif sort_by == "collect":
            query = query.order_by(XhsNote.collect_count.desc())
        elif sort_by == "time":
            query = query.order_by(XhsNote.publish_time.desc())
        else:
            # 默认按热度（点赞+评论+收藏综合排序）
            query = query.order_by(
                (XhsNote.like_count + XhsNote.comment_count * 2 + XhsNote.collect_count * 3).desc()
            )
        
        # 计算总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * page_size
        items = query.offset(offset).limit(page_size).all()
        
        return NoteListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
    
    def get_by_id(self, note_id: int) -> Optional[XhsNote]:
        """根据ID获取笔记详情"""
        cache_key = f"xhs:note:{note_id}"
        
        # 尝试从Redis缓存获取
        try:
            cached = self.redis.get(cache_key)
            if cached:
                pass  # 缓存存在，但还是从数据库获取完整对象
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
        
        # 从数据库获取
        note = self.db.query(XhsNote).filter(
            and_(XhsNote.id == note_id, XhsNote.status == 1)
        ).first()
        
        if note:
            # 更新缓存
            try:
                self.redis.set(cache_key, json.dumps({
                    "id": note.id,
                    "title": note.title,
                    "like_count": note.like_count
                }, ensure_ascii=False), ex=1800)
            except Exception as e:
                logger.warning(f"Redis写入失败: {e}")
        
        return note
    
    def _call_xhs_api(
        self,
        keyword: str,
        sort_by: Optional[str] = None
    ) -> List[dict]:
        """调用小红书API搜索笔记"""
        api_key = settings.XHS_API_KEY
        if not api_key:
            logger.warning("小红书API Key未配置，跳过搜索")
            return []
        
        try:
            url = "https://api.xiaohongshu.com/v1/search/notes"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            params = {
                "keyword": keyword,
                "page": 1,
                "page_size": 20,
                "sort": sort_by or "general"  # general/likes/time
            }
            
            with httpx.Client(timeout=15) as client:
                response = client.get(url, headers=headers, params=params)
                data = response.json()
            
            if data.get("success") and data.get("data", {}).get("notes"):
                results = []
                for note in data["data"]["notes"]:
                    content = note.get("desc", "")
                    evaluation = self._extract_key_evaluation(content)
                    
                    results.append({
                        "title": note.get("title", ""),
                        "author": note.get("user", {}).get("nickname", ""),
                        "author_avatar": note.get("user", {}).get("avatar", ""),
                        "content": content,
                        "like_count": note.get("liked_count", 0),
                        "comment_count": note.get("comment_count", 0),
                        "collect_count": note.get("collected_count", 0),
                        "original_url": note.get("note_url", ""),
                        "images": note.get("images", []),
                        "source_id": note.get("note_id", ""),
                        **evaluation
                    })
                return results
        except Exception as e:
            logger.error(f"小红书API调用失败: {e}")
        
        return []
    
    def _extract_key_evaluation(self, content: str) -> dict:
        """使用NLP提取关键评价（基于关键词匹配的轻量级方案）"""
        if not content:
            return {"pros": [], "cons": [], "tips": [], "summary": ""}
        
        sentences = re.split(r'[。！？\n.!?\n]', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        pros = []
        cons = []
        tips = []
        
        for sentence in sentences:
            # 检测优点
            for keyword in PROS_KEYWORDS:
                if keyword in sentence and sentence not in pros:
                    pros.append(sentence)
                    break
            
            # 检测缺点
            for keyword in CONS_KEYWORDS:
                if keyword in sentence and sentence not in cons:
                    cons.append(sentence)
                    break
            
            # 检测避坑提示
            for keyword in TIPS_KEYWORDS:
                if keyword in sentence and sentence not in tips:
                    tips.append(sentence)
                    break
        
        # 生成摘要（取前2句或前100字）
        summary = ""
        if sentences:
            summary_parts = []
            char_count = 0
            for s in sentences[:3]:
                if char_count + len(s) > 150:
                    break
                summary_parts.append(s)
                char_count += len(s)
            summary = "。".join(summary_parts)
            if len(summary) > 150:
                summary = summary[:150] + "..."
        
        return {
            "pros": pros[:5],  # 最多5条
            "cons": cons[:5],
            "tips": tips[:5],
            "summary": summary
        }
    
    def _save_notes_to_db(
        self,
        api_results: List[dict],
        merchant_id: Optional[int] = None,
        attraction_id: Optional[int] = None
    ) -> None:
        """将API结果保存到数据库"""
        for item in api_results:
            # 通过source_id去重
            existing = self.db.query(XhsNote).filter(
                XhsNote.source_id == item.get("source_id")
            ).first()
            if existing:
                continue
            
            note = XhsNote(
                merchant_id=merchant_id,
                attraction_id=attraction_id,
                title=item.get("title", ""),
                author=item.get("author", ""),
                author_avatar=item.get("author_avatar"),
                publish_time=datetime.now(),
                like_count=item.get("like_count", 0),
                comment_count=item.get("comment_count", 0),
                collect_count=item.get("collect_count", 0),
                content=item.get("content", ""),
                summary=item.get("summary", ""),
                pros=item.get("pros", []),
                cons=item.get("cons", []),
                tips=item.get("tips", []),
                original_url=item.get("original_url", ""),
                images=item.get("images", []),
                source="xiaohongshu",
                source_id=item.get("source_id", "")
            )
            self.db.add(note)
        
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"保存小红书笔记失败: {e}")
            self.db.rollback()
