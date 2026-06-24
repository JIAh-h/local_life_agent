import hashlib
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.share import ShareLog
from app.models.merchant import Merchant
from app.models.attraction import Attraction
from app.schemas.share import ShareCreate, ShareResponse
from app.config import settings

logger = logging.getLogger(__name__)


class ShareService:
    """分享服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_share(self, user_id: int, share_data: ShareCreate) -> ShareResponse:
        """生成分享链接"""
        # 验证分享对象是否存在
        self._validate_share_target(share_data.share_type, share_data.share_id)
        
        # 生成分享链接
        share_url = self._generate_share_url(
            share_data.share_type,
            share_data.share_id,
            share_data.share_channel,
            user_id
        )
        
        # 保存分享记录到数据库
        share_log = ShareLog(
            user_id=user_id,
            share_type=share_data.share_type,
            share_id=share_data.share_id,
            share_channel=share_data.share_channel,
            share_url=share_url,
            view_count=0
        )
        self.db.add(share_log)
        self.db.commit()
        self.db.refresh(share_log)
        
        # 如果是微信分享，调用微信分享接口
        if share_data.share_channel in ["wechat", "moments"]:
            title, description = self._get_share_content(share_data.share_type, share_data.share_id)
            self._call_wechat_share(share_url, title, description)
        
        return ShareResponse(
            id=share_log.id,
            user_id=share_log.user_id,
            share_type=share_log.share_type,
            share_id=share_log.share_id,
            share_channel=share_log.share_channel,
            share_url=share_log.share_url,
            view_count=share_log.view_count,
            created_at=share_log.created_at
        )
    
    def track_view(self, share_id: int) -> None:
        """记录分享链接被访问"""
        share_log = self.db.query(ShareLog).filter(ShareLog.id == share_id).first()
        if share_log:
            share_log.view_count += 1
            self.db.commit()
    
    def get_share_stats(self, user_id: int) -> dict:
        """获取用户分享统计"""
        total_shares = self.db.query(ShareLog).filter(
            ShareLog.user_id == user_id
        ).count()
        
        total_views = self.db.query(
            ShareLog.view_count
        ).filter(
            ShareLog.user_id == user_id
        ).all()
        
        total_view_count = sum(v[0] for v in total_views)
        
        # 按渠道统计
        channel_stats = self.db.query(
            ShareLog.share_channel,
            ShareLog.id  # 使用id计数
        ).filter(
            ShareLog.user_id == user_id
        ).all()
        
        channels = {}
        for channel, _ in channel_stats:
            channels[channel] = channels.get(channel, 0) + 1
        
        return {
            "total_shares": total_shares,
            "total_views": total_view_count,
            "channels": channels
        }
    
    def _validate_share_target(self, share_type: str, share_id: int) -> None:
        """验证分享目标是否存在"""
        if share_type == "merchant":
            merchant = self.db.query(Merchant).filter(
                and_(Merchant.id == share_id, Merchant.status == 1)
            ).first()
            if not merchant:
                raise ValueError("商家不存在或已下架")
        elif share_type == "attraction":
            attraction = self.db.query(Attraction).filter(
                and_(Attraction.id == share_id, Attraction.status == 1)
            ).first()
            if not attraction:
                raise ValueError("景点不存在或已下架")
        else:
            raise ValueError(f"不支持的分享类型: {share_type}")
    
    def _generate_share_url(
        self,
        share_type: str,
        share_id: int,
        share_channel: str,
        user_id: int
    ) -> str:
        """生成分享链接"""
        # 生成唯一标识
        raw = f"{share_type}:{share_id}:{user_id}:{datetime.now().timestamp()}"
        share_token = hashlib.md5(raw.encode()).hexdigest()[:12]
        
        # 基础URL
        base_url = "http://localhost:5174"  # 前端地址
        
        # 根据分享类型生成链接
        if share_type == "merchant":
            path = f"/food/{share_id}"
        elif share_type == "attraction":
            path = f"/attraction/{share_id}"
        else:
            path = f"/{share_type}/{share_id}"
        
        # 添加分享参数
        url = f"{base_url}{path}?ref=share&token={share_token}&from={user_id}"
        
        # 如果是链接分享，添加渠道标识
        if share_channel == "link":
            url += "&channel=link"
        
        return url
    
    def _get_share_content(self, share_type: str, share_id: int) -> tuple:
        """获取分享内容（标题和描述）"""
        if share_type == "merchant":
            merchant = self.db.query(Merchant).filter(Merchant.id == share_id).first()
            if merchant:
                title = f"推荐美食：{merchant.name}"
                description = f"{merchant.category} | 评分{merchant.rating} | 人均¥{merchant.avg_price}"
                return title, description
        elif share_type == "attraction":
            attraction = self.db.query(Attraction).filter(Attraction.id == share_id).first()
            if attraction:
                title = f"推荐景点：{attraction.name}"
                price_info = "免费" if float(attraction.ticket_price or 0) == 0 else f"¥{attraction.ticket_price}"
                description = f"{attraction.category} | 评分{attraction.rating} | 门票{price_info}"
                return title, description
        
        return "小紫薯", "发现身边好去处"
    
    def _call_wechat_share(self, share_url: str, title: str, description: str) -> bool:
        """调用微信分享接口（JS-SDK配置生成）"""
        try:
            # 实际项目中，这里需要：
            # 1. 获取access_token
            # 2. 获取jsapi_ticket
            # 3. 生成签名
            # 4. 返回配置信息给前端
            
            # 模拟返回
            logger.info(f"微信分享配置: url={share_url}, title={title}")
            
            # 这里可以集成微信公众号API
            # 需要配置 WECHAT_APPID 和 WECHAT_SECRET
            
            return True
        except Exception as e:
            logger.error(f"微信分享配置失败: {e}")
            return False
