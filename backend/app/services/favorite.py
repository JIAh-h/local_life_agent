import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.models.favorite import UserFavorite
from app.models.xhs import XhsNote, XhsComment
from app.schemas.favorite import FavoriteCreate, FavoriteListResponse, FavoriteResponse, CommentItem

logger = logging.getLogger(__name__)


class FavoriteService:
    def __init__(self, db: Session):
        self.db = db

    def get_favorites(
        self, user_id: int, category: Optional[int] = None,
        page: int = 1, page_size: int = 20
    ) -> FavoriteListResponse:
        query = self.db.query(UserFavorite).filter(UserFavorite.user_id == user_id)
        if category:
            query = query.filter(UserFavorite.category == category)
        query = query.order_by(UserFavorite.created_at.desc())
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        # 构建响应，附加笔记信息和评论
        result = []
        for f in items:
            note = f.note
            # 从 xhs_comments 读取评论并构建树形结构
            all_comments = self.db.query(XhsComment).filter(
                XhsComment.note_id == f.note_id,
                XhsComment.parent_id.is_(None),  # 只取主评论
            ).order_by(XhsComment.id.asc()).all()

            comment_items = []
            for c in all_comments:
                # 查子评论
                subs = self.db.query(XhsComment).filter(
                    XhsComment.note_id == f.note_id,
                    XhsComment.parent_id == c.comment_id,
                ).order_by(XhsComment.id.asc()).all()
                sub_items = [
                    CommentItem(
                        id=s.comment_id, content=s.content or "",
                        create_time=s.create_time or "", ip_location=s.ip_location or "",
                        like_count=s.like_count or 0,
                        user_nickname=s.user_nickname or "",
                        user_image=s.user_avatar or "",
                    ) for s in subs
                ]
                comment_items.append(CommentItem(
                    id=c.comment_id, content=c.content or "",
                    create_time=c.create_time or "", ip_location=c.ip_location or "",
                    like_count=c.like_count or 0,
                    user_nickname=c.user_nickname or "",
                    user_image=c.user_avatar or "",
                    sub_comments=sub_items,
                ))

            result.append(FavoriteResponse(
                id=f.id, user_id=f.user_id, note_id=f.note_id,
                category=f.category, created_at=f.created_at,
                note_title=note.display_title or "" if note else "",
                note_cover=note.cover_url or "" if note else "",
                note_author=note.author_name or "" if note else "",
                note_author_avatar=note.author_avatar or "" if note else "",
                note_publish_time=note.publish_time or "" if note else "",
                note_desc=(note.description or "")[:200] if note else "",
                note_like_count=note.like_count or 0 if note else 0,
                note_collect_count=note.collect_count or 0 if note else 0,
                note_image_urls=note.image_urls or [] if note else [],
                note_comment_count=len(comment_items),
                xsec_token=note.xsec_token or "" if note else "",
                comments=comment_items,
            ))
        return FavoriteListResponse(total=total, page=page, page_size=page_size, items=result)

    def add_favorite(self, user_id: int, data: FavoriteCreate) -> UserFavorite:
        # 检查重复
        existing = self.db.query(UserFavorite).filter(and_(
            UserFavorite.user_id == user_id,
            UserFavorite.note_id == data.note_id,
        )).first()
        if existing:
            raise ValueError("已经收藏过了")

        # 1. 同步写入 xhs_notes
        note = self.db.query(XhsNote).filter(XhsNote.note_id == data.note_id).first()
        if not note:
            note = XhsNote(
                note_id=data.note_id,
                xsec_token=data.xsec_token or "",
                display_title=data.display_title,
                cover_url=data.cover_url,
                image_urls=data.image_urls,
                description=data.description,
                author_name=data.author_name,
                author_avatar=data.author_avatar,
                publish_time=data.publish_time,
                like_count=data.like_count,
                collect_count=data.collect_count,
            )
            self.db.add(note)
            self.db.flush()
        else:
            # 更新已有笔记
            note.display_title = data.display_title or note.display_title
            note.cover_url = data.cover_url or note.cover_url
            note.image_urls = data.image_urls or note.image_urls
            note.description = data.description or note.description
            note.like_count = data.like_count or note.like_count
            note.collect_count = data.collect_count or note.collect_count

        # 2. 同步写入评论到 xhs_comments
        if data.comments:
            # 先清除旧评论（如果有）
            self.db.query(XhsComment).filter(
                XhsComment.note_id == data.note_id
            ).delete(synchronize_session="fetch")
            for c in data.comments:
                self._save_comment(c, data.note_id)
            self.db.flush()

        # 3. 创建收藏记录
        favorite = UserFavorite(
            user_id=user_id,
            note_id=data.note_id,
            category=data.category,
        )
        self.db.add(favorite)
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def _save_comment(self, c: "CommentItem", note_id: str) -> None:
        """递归保存一条评论及其子评论到 xhs_comments"""
        from app.schemas.favorite import CommentItem as CommentSchema
        comment = XhsComment(
            comment_id=c.id,
            note_id=note_id,
            content=c.content or "",
            create_time=c.create_time or "",
            ip_location=c.ip_location or "",
            like_count=c.like_count or 0,
            user_nickname=c.user_nickname or "",
            user_avatar=c.user_image or "",
        )
        self.db.add(comment)
        self.db.flush()  # 获取 id (虽然用 comment_id 管理, 但保证顺序)

        # 递归保存子评论
        for sub in c.sub_comments:
            if isinstance(sub, dict):
                sub_id = sub.get("id", "")
                sub_content = sub.get("content", "")
                sub_time = sub.get("create_time", "")
                sub_ip = sub.get("ip_location", "")
                sub_like = sub.get("like_count", 0)
                sub_nickname = sub.get("user_nickname", "")
                sub_image = sub.get("user_image", "")
            else:
                sub_id = sub.id
                sub_content = sub.content
                sub_time = sub.create_time
                sub_ip = sub.ip_location
                sub_like = sub.like_count
                sub_nickname = sub.user_nickname
                sub_image = sub.user_image
            sub_comment = XhsComment(
                comment_id=sub_id,
                note_id=note_id,
                parent_id=c.id,
                content=sub_content or "",
                create_time=sub_time or "",
                ip_location=sub_ip or "",
                like_count=sub_like or 0,
                user_nickname=sub_nickname or "",
                user_avatar=sub_image or "",
            )
            self.db.add(sub_comment)

    def _delete_note_with_cascade(self, note_id: str) -> None:
        """删除 xhs_notes 记录，数据库级联删除关联的 xhs_comments"""
        note = self.db.query(XhsNote).filter(XhsNote.note_id == note_id).first()
        if note:
            self.db.delete(note)
            logger.info(f"已级联删除笔记和评论: note_id={note_id}")
        else:
            logger.warning(f"笔记记录不存在（可能已删除）: note_id={note_id}")

    def remove_favorite(self, user_id: int, favorite_id: int) -> None:
        """
        取消收藏 — 事务内级联删除：
        1. user_favorites（收藏记录）
        2. xhs_notes（笔记，数据库自动 cascade 删除 xhs_comments）
        """
        favorite = self.db.query(UserFavorite).filter(and_(
            UserFavorite.id == favorite_id,
            UserFavorite.user_id == user_id,
        )).first()
        if not favorite:
            raise ValueError("收藏记录不存在")

        note_id = favorite.note_id
        self.db.delete(favorite)
        self._delete_note_with_cascade(note_id)
        self.db.commit()
        logger.info(f"取消收藏完成: user_id={user_id} favorite_id={favorite_id} note_id={note_id}")

    def batch_remove_favorites(self, user_id: int, favorite_ids: List[int]) -> None:
        """
        批量取消收藏 — 事务内级联删除
        """
        if not favorite_ids:
            raise ValueError("收藏ID列表不能为空")

        favorites = self.db.query(UserFavorite).filter(and_(
            UserFavorite.id.in_(favorite_ids),
            UserFavorite.user_id == user_id,
        )).all()
        if not favorites:
            raise ValueError("未找到指定的收藏记录")

        for fav in favorites:
            self.db.delete(fav)
            self._delete_note_with_cascade(fav.note_id)

        self.db.commit()
        logger.info(f"批量取消收藏完成: user_id={user_id} count={len(favorites)}")
