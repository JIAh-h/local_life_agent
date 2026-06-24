from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.share import ShareCreate, ShareResponse
from app.services.share import ShareService

router = APIRouter()

@router.post("/generate", response_model=ShareResponse)
async def generate_share_link(
    share_data: ShareCreate,
    user_id: int,
    db: Session = Depends(get_db)
):
    """生成分享链接"""
    share_service = ShareService(db)
    return share_service.generate_share(user_id, share_data)
