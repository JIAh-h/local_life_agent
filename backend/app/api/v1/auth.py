from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import Dict, Any, Optional
import uuid
import hashlib
import base64
from io import BytesIO

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserLoginByWechat,
    UserLoginByQQ,
    ForgotPassword,
    ResetPassword,
    ChangePassword,
    UserUpdate,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    CaptchaResponse,
    SendSmsCodeRequest,
    SendSmsCodeResponse,
    VerifySmsCodeRequest,
    UserStatusResponse,
    PasswordStrengthResponse
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    store_tokens_in_redis,
    get_token_from_redis,
    remove_token_from_redis,
    blacklist_token,
    revoke_all_user_tokens,
    refresh_access_token,
    get_user_id_from_token,
    hash_password,
    verify_password
)
from app.config import settings
from app.dependencies import get_current_user
from app.redis_client import get_redis

# 内存缓存（Redis不可用时的后备方案）
import threading
_memory_cache = {}
_memory_cache_lock = threading.Lock()

def _get_cache():
    """获取缓存存储 - 优先Redis，失败时使用内存"""
    try:
        r = get_redis()
        r.ping()
        return ("redis", r)
    except Exception:
        return ("memory", _memory_cache)

def _cache_set(key, value, expire=300):
    """设置缓存"""
    cache_type, cache = _get_cache()
    if cache_type == "redis":
        cache.setex(key, expire, value)
    else:
        import time
        with _memory_cache_lock:
            cache[key] = (value, time.time() + expire)

def _cache_get(key):
    """获取缓存"""
    cache_type, cache = _get_cache()
    if cache_type == "redis":
        val = cache.get(key)
        return val
    else:
        import time
        with _memory_cache_lock:
            if key in cache:
                val, expires = cache[key]
                if time.time() < expires:
                    return val
                del cache[key]
        return None

def _cache_delete(key):
    """删除缓存"""
    cache_type, cache = _get_cache()
    if cache_type == "redis":
        cache.delete(key)
    else:
        with _memory_cache_lock:
            cache.pop(key, None)

router = APIRouter()

# 验证码相关常量
CAPTCHA_PREFIX = "captcha:"
SMS_CODE_PREFIX = "sms_code:"
RESET_TOKEN_PREFIX = "reset_token:"


def generate_captcha_key() -> str:
    """生成验证码key"""
    return str(uuid.uuid4())


def generate_captcha_code() -> str:
    """生成4位图形验证码（字母+数字）"""
    import random
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=4))


def generate_sms_code() -> str:
    """生成6位数字短信验证码"""
    import random
    return ''.join(random.choices('0123456789', k=6))


def generate_captcha_image(code: str) -> str:
    """生成验证码图片（Base64编码）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import random

        # 创建图片
        width, height = 120, 40
        image = Image.new('RGB', (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(image)

        # 添加干扰线
        for _ in range(5):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)], fill=(random.randint(0, 200), random.randint(0, 200), random.randint(0, 200)))

        # 添加干扰点
        for _ in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=(random.randint(0, 200), random.randint(0, 200), random.randint(0, 200)))

        # 绘制文字
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except Exception:
            font = ImageFont.load_default()

        for i, char in enumerate(code):
            x = 10 + i * 25
            y = random.randint(5, 15)
            draw.text((x, y), char, font=font, fill=(random.randint(0, 80), random.randint(0, 80), random.randint(0, 80)))

        # 转换为Base64
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except ImportError:
        # 没有PIL时生成一个可见的SVG图片作为替代
        import random as _rnd
        colors = ["#d32f2f", "#1976d2", "#388e3c", "#f57c00", "#7b1fa2"]
        svg_parts = []
        for i, ch in enumerate(code):
            x = 20 + i * 28
            y = 30
            color = _rnd.choice(colors)
            angle = _rnd.randint(-20, 20)
            svg_parts.append(
                f'<text x="{x}" y="{y}" font-size="26" font-weight="bold" '
                f'fill="{color}" transform="rotate({angle},{x},{y})" '
                f'font-family="Arial, sans-serif">{ch}</text>'
            )
        # 干扰线
        lines = ""
        for _ in range(4):
            lines += f'<line x1="{_rnd.randint(0,100)}" y1="{_rnd.randint(0,40)}" x2="{_rnd.randint(0,100)}" y2="{_rnd.randint(0,40)}" stroke="{_rnd.choice(colors)}" stroke-width="1" opacity="0.5"/>'
        # 干扰点
        dots = ""
        for _ in range(40):
            dots += f'<circle cx="{_rnd.randint(0,120)}" cy="{_rnd.randint(0,40)}" r="1.5" fill="{_rnd.choice(colors)}" opacity="0.4"/>'

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" viewBox="0 0 120 40">'
            f'<rect width="120" height="40" fill="#f5f5f5" rx="4"/>'
            f'{lines}{dots}{"".join(svg_parts)}</svg>'
        )
        b64 = base64.b64encode(svg.encode()).decode()
        return f"data:image/svg+xml;base64,{b64}"


def verify_captcha(captcha_key: str, captcha_code: str) -> bool:
    """验证验证码"""
    key = f"{CAPTCHA_PREFIX}{captcha_key}"
    stored_code = _cache_get(key)

    if stored_code and stored_code.lower() == captcha_code.lower():
        # 验证成功后删除验证码
        _cache_delete(key)
        return True
    return False


def generate_reset_token() -> str:
    """生成密码重置令牌"""
    return str(uuid.uuid4())


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    用户注册
    
    创建新用户并返回用户信息
    """
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查手机号是否已存在
    existing_phone = db.query(User).filter(User.phone == user_data.phone).first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已被注册"
        )
    
    # 检查邮箱是否已存在（如果提供了邮箱）
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
    
    # 创建新用户
    hashed_password = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        hashed_password=hashed_password,
        phone=user_data.phone,
        email=user_data.email,
        nickname=user_data.nickname or user_data.username,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录
    
    支持多种登录方式：
    1. 用户名/手机号/邮箱 + 密码 + 验证码
    2. 微信登录（预留）
    3. QQ登录（预留）
    """
    # 验证验证码
    if not verify_captcha(user_data.captcha_key, user_data.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )
    
    user = None
    
    if user_data.login_type == "password":
        # 密码登录
        if not user_data.username or not user_data.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名和密码不能为空"
            )
        
        # 支持用户名、手机号、邮箱登录
        user = db.query(User).filter(
            (User.username == user_data.username) |
            (User.phone == user_data.username) |
            (User.email == user_data.username)
        ).first()
        
        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 检查账户状态
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被禁用"
            )
        
        # 检查账户是否被锁定
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"账户已被锁定，请稍后再试"
            )
        
        # 重置登录尝试次数
        user.login_attempts = 0
        user.locked_until = None
        
    elif user_data.login_type == "wechat":
        # 微信登录
        if not user_data.openid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="微信openid不能为空"
            )
        
        user = db.query(User).filter(User.openid == user_data.openid).first()
        if not user:
            # 可以自动创建用户或提示注册
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="微信用户未注册，请先注册"
            )
        
    elif user_data.login_type == "qq":
        # QQ登录
        if not user_data.qq_openid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QQ openid不能为空"
            )
        
        user = db.query(User).filter(User.qq_openid == user_data.qq_openid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QQ用户未注册，请先注册"
            )
    
    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    db.commit()
    
    # 根据"记住我"设置Token过期时间
    if user_data.remember_me:
        access_token_expires = timedelta(days=7)  # 记住我时，Access Token 7天过期
        refresh_token_expires = timedelta(days=30)  # Refresh Token 30天过期
    else:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # 生成Token对
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        expires_delta=refresh_token_expires
    )
    
    # 将Token写入Redis
    store_tokens_in_redis(
        user_id=user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        device_info=user_data.device_info
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int(access_token_expires.total_seconds()),
        "remember_me": user_data.remember_me
    }


@router.post("/login/wechat", response_model=TokenResponse)
async def login_by_wechat(user_data: UserLoginByWechat, db: Session = Depends(get_db)):
    """
    微信登录（预留接口）
    
    使用微信code登录
    """
    # TODO: 实现微信登录逻辑
    # 1. 使用code调用微信接口获取openid
    # 2. 查找或创建用户
    # 3. 生成Token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="微信登录功能尚未实现"
    )


@router.post("/login/qq", response_model=TokenResponse)
async def login_by_qq(user_data: UserLoginByQQ, db: Session = Depends(get_db)):
    """
    QQ登录（预留接口）
    
    使用QQ code登录
    """
    # TODO: 实现QQ登录逻辑
    # 1. 使用code调用QQ接口获取openid
    # 2. 查找或创建用户
    # 3. 生成Token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="QQ登录功能尚未实现"
    )


@router.post("/forgot-password", response_model=SendSmsCodeResponse)
async def forgot_password(request: ForgotPassword, db: Session = Depends(get_db)):
    """
    忘记密码
    
    发送密码重置验证码
    """
    # 验证验证码
    if not verify_captcha(request.captcha_key, request.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图形验证码错误或已过期"
        )
    
    # 检查手机号是否存在
    user = db.query(User).filter(User.phone == request.phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该手机号未注册"
        )
    
    # 生成短信验证码（这里模拟，实际应该调用短信服务）
    sms_code = generate_sms_code()
    
    # 存储短信验证码
    key = f"{SMS_CODE_PREFIX}reset_password:{request.phone}"
    _cache_set(key, sms_code, 300)  # 5分钟过期
    
    # 生成重置令牌
    reset_token = generate_reset_token()
    reset_key = f"{RESET_TOKEN_PREFIX}{request.phone}"
    _cache_set(reset_key, reset_token, 3600)  # 1小时过期
    
    # TODO: 实际应该调用短信服务发送验证码
    # send_sms(request.phone, f"您的密码重置验证码是：{sms_code}，5分钟内有效。")
    print(f"[SMS] 手机号: {request.phone}, 验证码: {sms_code}, 用途: reset_password")
    
    return {
        "success": True,
        "message": "验证码已发送到您的手机",
        "expires_in": 300
    }


@router.post("/reset-password")
async def reset_password(request: ResetPassword, db: Session = Depends(get_db)):
    """
    重置密码
    
    使用验证码重置密码
    """
    # 验证短信验证码
    sms_key = f"{SMS_CODE_PREFIX}reset_password:{request.phone}"
    stored_code = _cache_get(sms_key)
    
    if not stored_code or stored_code != request.captcha_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="短信验证码错误或已过期"
        )
    
    # 验证重置令牌
    reset_key = f"{RESET_TOKEN_PREFIX}{request.phone}"
    stored_token = _cache_get(reset_key)
    
    if not stored_token or stored_token != request.reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置令牌无效或已过期"
        )
    
    # 查找用户
    user = db.query(User).filter(User.phone == request.phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新密码
    user.hashed_password = hash_password(request.new_password)
    user.login_attempts = 0
    user.locked_until = None
    db.commit()
    
    # 删除验证码和重置令牌
    _cache_delete(sms_key)
    _cache_delete(reset_key)
    
    # 撤销所有Token（强制重新登录）
    revoke_all_user_tokens(user.id)
    
    return {"message": "密码重置成功，请重新登录"}


@router.post("/change-password")
async def change_password(
    request: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改密码
    
    需要验证原密码
    """
    # 验证原密码
    if not verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )
    
    # 更新密码
    current_user.hashed_password = hash_password(request.new_password)
    db.commit()
    
    # 撤销所有Token（强制重新登录）
    revoke_all_user_tokens(current_user.id)
    
    return {"message": "密码修改成功，请重新登录"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    刷新Token
    
    使用Refresh Token获取新的Token对
    """
    result = refresh_access_token(request.refresh_token)
    return {
        **result,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "remember_me": False
    }


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(lambda x: x.headers.get("Authorization", "").replace("Bearer ", ""))
):
    """
    用户登出
    
    将当前Token加入黑名单
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No token provided"
        )
    
    blacklist_token(token, "access")
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all_devices(
    current_user: User = Depends(get_current_user)
):
    """
    登出所有设备
    
    撤销用户的所有Token
    """
    revoke_all_user_tokens(current_user.id)
    return {"message": "Successfully logged out from all devices"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户信息
    
    返回当前登录用户的详细信息
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_info(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新当前用户信息
    
    更新昵称、头像、邮箱、手机号等信息
    """
    # 检查邮箱是否已被其他用户使用
    if user_data.email:
        existing_email = db.query(User).filter(
            User.email == user_data.email,
            User.id != current_user.id
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被其他用户使用"
            )
    
    # 检查手机号是否已被其他用户使用
    if user_data.phone:
        existing_phone = db.query(User).filter(
            User.phone == user_data.phone,
            User.id != current_user.id
        ).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号已被其他用户使用"
            )
    
    # 更新用户信息
    if user_data.nickname is not None:
        current_user.nickname = user_data.nickname
    if user_data.avatar_url is not None:
        current_user.avatar_url = user_data.avatar_url
    if user_data.email is not None:
        current_user.email = user_data.email
    if user_data.phone is not None:
        current_user.phone = user_data.phone
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.get("/verify-token")
async def verify_user_token(
    current_user: User = Depends(get_current_user)
):
    """
    验证Token有效性
    
    检查当前Token是否有效
    """
    return {
        "valid": True,
        "user_id": current_user.id,
        "message": "Token is valid"
    }


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha():
    """
    获取验证码
    
    生成图形验证码
    """
    captcha_key = generate_captcha_key()
    captcha_code = generate_captcha_code()
    
    # 存储验证码到缓存
    key = f"{CAPTCHA_PREFIX}{captcha_key}"
    _cache_set(key, captcha_code, 300)  # 5分钟过期
    
    # 生成验证码图片
    captcha_image = generate_captcha_image(captcha_code)
    
    return {
        "captcha_key": captcha_key,
        "captcha_image": captcha_image,
        "expires_in": 300
    }


@router.post("/verify-captcha")
async def verify_captcha_endpoint(captcha_key: str, captcha_code: str):
    """
    验证验证码
    
    验证图形验证码
    """
    if verify_captcha(captcha_key, captcha_code):
        return {"valid": True, "message": "验证码正确"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )


@router.post("/send-sms-code", response_model=SendSmsCodeResponse)
async def send_sms_code(request: SendSmsCodeRequest, db: Session = Depends(get_db)):
    """
    发送短信验证码
    
    发送验证码到手机
    """
    # 检查手机号是否已注册（根据用途）
    if request.purpose == "register":
        existing_user = db.query(User).filter(User.phone == request.phone).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已注册"
            )
    elif request.purpose in ["login", "reset_password"]:
        existing_user = db.query(User).filter(User.phone == request.phone).first()
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该手机号未注册"
            )
    
    # 生成短信验证码
    sms_code = generate_sms_code()
    
    # 存储验证码
    key = f"{SMS_CODE_PREFIX}{request.purpose}:{request.phone}"
    _cache_set(key, sms_code, 300)  # 5分钟过期
    
    # TODO: 实际应该调用短信服务发送验证码
    # send_sms(request.phone, f"您的验证码是：{sms_code}，5分钟内有效。")
    print(f"[SMS] 手机号: {request.phone}, 验证码: {sms_code}, 用途: {request.purpose}")
    
    return {
        "success": True,
        "message": "验证码已发送",
        "expires_in": 300
    }


@router.post("/verify-sms-code")
async def verify_sms_code(request: VerifySmsCodeRequest):
    """
    验证短信验证码
    
    验证手机验证码
    """
    key = f"{SMS_CODE_PREFIX}{request.purpose}:{request.phone}"
    stored_code = _cache_get(key)
    
    if stored_code and stored_code == request.code:
        # 验证成功后删除验证码
        _cache_delete(key)
        return {"valid": True, "message": "验证码正确"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )


@router.get("/status", response_model=UserStatusResponse)
async def get_user_status(
    current_user: User = Depends(get_current_user)
):
    """
    获取用户状态
    
    返回账户状态信息
    """
    is_locked = current_user.locked_until and current_user.locked_until > datetime.utcnow()
    
    return {
        "is_active": current_user.is_active,
        "is_locked": is_locked,
        "locked_until": current_user.locked_until,
        "login_attempts": current_user.login_attempts
    }


@router.get("/password-strength", response_model=PasswordStrengthResponse)
async def check_password_strength(password: str):
    """
    检查密码强度
    
    返回密码强度评估
    """
    score = 0
    suggestions = []
    
    # 长度检查
    if len(password) >= 6:
        score += 20
    else:
        suggestions.append("密码长度至少6位")
    
    # 包含小写字母
    if re.search(r'[a-z]', password):
        score += 20
    else:
        suggestions.append("建议包含小写字母")
    
    # 包含大写字母
    if re.search(r'[A-Z]', password):
        score += 20
    else:
        suggestions.append("建议包含大写字母")
    
    # 包含数字
    if re.search(r'\d', password):
        score += 20
    else:
        suggestions.append("建议包含数字")
    
    # 包含特殊字符
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 20
    else:
        suggestions.append("建议包含特殊字符")
    
    # 确定强度等级
    if score < 40:
        level = "weak"
    elif score < 60:
        level = "medium"
    elif score < 80:
        level = "strong"
    else:
        level = "very_strong"
    
    return {
        "score": score,
        "level": level,
        "suggestions": suggestions
    }


# 辅助函数
import re