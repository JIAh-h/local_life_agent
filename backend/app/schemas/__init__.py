from app.schemas.user import UserRegister, UserUpdate, UserResponse
from app.schemas.location import LocationCreate, LocationUpdate, LocationResponse, LocationSetRequest
from app.schemas.merchant import MerchantCreate, MerchantUpdate, MerchantResponse, MerchantListResponse
from app.schemas.attraction import AttractionCreate, AttractionUpdate, AttractionResponse, AttractionListResponse
from app.schemas.xiaohongshu import NoteCreate, NoteUpdate, NoteResponse, NoteListResponse
from app.schemas.chat import ChatMessage, ChatResponse, ChatHistoryResponse
from app.schemas.favorite import FavoriteCreate, FavoriteResponse, FavoriteListResponse
from app.schemas.share import ShareCreate, ShareResponse
from app.schemas.recommend import RecommendationResponse, RecommendationFeedback

__all__ = [
    "UserRegister",
    "UserUpdate",
    "UserResponse",
    "LocationCreate",
    "LocationUpdate",
    "LocationResponse",
    "LocationSetRequest",
    "MerchantCreate",
    "MerchantUpdate",
    "MerchantResponse",
    "MerchantListResponse",
    "AttractionCreate",
    "AttractionUpdate",
    "AttractionResponse",
    "AttractionListResponse",
    "NoteCreate",
    "NoteUpdate",
    "NoteResponse",
    "NoteListResponse",
    "ChatMessage",
    "ChatResponse",
    "ChatHistoryResponse",
    "FavoriteCreate",
    "FavoriteResponse",
    "FavoriteListResponse",
    "ShareCreate",
    "ShareResponse",
    "RecommendationResponse",
    "RecommendationFeedback",
]
