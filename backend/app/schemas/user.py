from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional, Union
from datetime import datetime
import re


class UserBase(BaseModel):
    """用户基础模型"""
    nickname: Optional[str] = Field(None, max_length=32, description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="头像URL或Base64")


class UserRegister(BaseModel):
    """用户注册模型"""
    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    confirm_password: str = Field(..., description="确认密码")
    phone: str = Field(..., description="手机号")
    email: Optional[str] = Field(None, description="邮箱")
    nickname: Optional[str] = Field(None, max_length=32, description="用户昵称")
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名：3-32位，只能包含字母、数字、下划线"""
        if not re.match(r'^[a-zA-Z0-9_]{3,32}$', v):
            raise ValueError('用户名必须是3-32位，只能包含字母、数字、下划线')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度：至少6位"""
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v
    
    @validator('confirm_password')
    def validate_confirm_password(cls, v, values):
        """验证确认密码"""
        if 'password' in values and v != values['password']:
            raise ValueError('两次输入的密码不一致')
        return v
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入有效的手机号')
        return v
    
    @validator('email')
    def validate_email(cls, v):
        """验证邮箱格式"""
        if v is not None and v.strip() != '':
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError('请输入有效的邮箱地址')
        return v


class UserLogin(BaseModel):
    """用户登录模型"""
    login_type: str = Field("password", description="登录类型：password/wechat/qq")
    username: Optional[str] = Field(None, description="用户名/手机号/邮箱")
    password: Optional[str] = Field(None, description="密码")
    captcha_key: str = Field(..., description="验证码key")
    captcha_code: str = Field(..., description="验证码")
    openid: Optional[str] = Field(None, description="微信openid")
    qq_openid: Optional[str] = Field(None, description="QQ openid")
    device_info: Optional[str] = Field(None, description="设备信息")
    remember_me: bool = Field(False, description="记住我")
    
    @validator('login_type')
    def validate_login_type(cls, v):
        """验证登录类型"""
        allowed_types = ['password', 'wechat', 'qq']
        if v not in allowed_types:
            raise ValueError(f'登录类型必须是: {", ".join(allowed_types)}')
        return v
    
    @validator('username')
    def validate_username_for_password_login(cls, v, values):
        """密码登录时验证用户名"""
        if values.get('login_type') == 'password' and not v:
            raise ValueError('密码登录时用户名不能为空')
        return v
    
    @validator('password')
    def validate_password_for_password_login(cls, v, values):
        """密码登录时验证密码"""
        if values.get('login_type') == 'password' and not v:
            raise ValueError('密码登录时密码不能为空')
        return v


class UserLoginByWechat(BaseModel):
    """微信登录模型"""
    code: str = Field(..., description="微信登录code")
    device_info: Optional[str] = Field(None, description="设备信息")
    remember_me: bool = Field(False, description="记住我")


class UserLoginByQQ(BaseModel):
    """QQ登录模型"""
    code: str = Field(..., description="QQ登录code")
    device_info: Optional[str] = Field(None, description="设备信息")
    remember_me: bool = Field(False, description="记住我")


class ForgotPassword(BaseModel):
    """忘记密码模型"""
    phone: str = Field(..., description="手机号")
    captcha_key: str = Field(..., description="验证码key")
    captcha_code: str = Field(..., description="验证码")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入有效的手机号')
        return v


class ResetPassword(BaseModel):
    """重置密码模型"""
    phone: str = Field(..., description="手机号")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码")
    confirm_password: str = Field(..., description="确认新密码")
    captcha_key: str = Field(..., description="验证码key")
    captcha_code: str = Field(..., description="验证码")
    reset_token: str = Field(..., description="重置令牌")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """验证新密码强度"""
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v
    
    @validator('confirm_password')
    def validate_confirm_password(cls, v, values):
        """验证确认密码"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('两次输入的密码不一致')
        return v


class ChangePassword(BaseModel):
    """修改密码模型"""
    old_password: str = Field(..., description="原密码")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码")
    confirm_password: str = Field(..., description="确认新密码")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """验证新密码强度"""
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v
    
    @validator('confirm_password')
    def validate_confirm_password(cls, v, values):
        """验证确认密码"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('两次输入的密码不一致')
        return v


class UserUpdate(BaseModel):
    """更新用户模型"""
    nickname: Optional[str] = Field(None, max_length=32, description="用户昵称")
    avatar_url: Optional[str] = Field(None, max_length=2097152, description="头像URL或Base64")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    
    @validator('email')
    def validate_email(cls, v):
        """验证邮箱格式"""
        if v is not None and v.strip() != '':
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError('请输入有效的邮箱地址')
        return v
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if v is not None and v.strip() != '':
            if not re.match(r'^1[3-9]\d{9}$', v):
                raise ValueError('请输入有效的11位手机号')
        return v


class UserResponse(UserBase):
    """用户响应模型"""
    id: int = Field(..., description="用户ID")
    username: Optional[str] = Field(None, description="用户名")
    phone: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")
    is_active: bool = Field(True, description="账户是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_login: Optional[datetime] = Field(None, description="最后登录时间")
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")
    remember_me: bool = Field(False, description="是否记住我")


class RefreshTokenRequest(BaseModel):
    """刷新Token请求模型"""
    refresh_token: str = Field(..., description="刷新令牌")


class CaptchaResponse(BaseModel):
    """验证码响应模型"""
    captcha_key: str = Field(..., description="验证码key")
    captcha_image: str = Field(..., description="验证码图片Base64")
    expires_in: int = Field(..., description="验证码过期时间（秒）")


class SendSmsCodeRequest(BaseModel):
    """发送短信验证码请求模型"""
    phone: str = Field(..., description="手机号")
    purpose: str = Field("register", description="用途：register/login/reset_password")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入有效的手机号')
        return v
    
    @validator('purpose')
    def validate_purpose(cls, v):
        """验证用途"""
        allowed_purposes = ['register', 'login', 'reset_password']
        if v not in allowed_purposes:
            raise ValueError(f'用途必须是: {", ".join(allowed_purposes)}')
        return v


class SendSmsCodeResponse(BaseModel):
    """发送短信验证码响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
    expires_in: int = Field(..., description="验证码过期时间（秒）")


class VerifySmsCodeRequest(BaseModel):
    """验证短信验证码请求模型"""
    phone: str = Field(..., description="手机号")
    code: str = Field(..., description="验证码")
    purpose: str = Field("register", description="用途：register/login/reset_password")
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入有效的手机号')
        return v


class UserStatusResponse(BaseModel):
    """用户状态响应模型"""
    is_active: bool = Field(..., description="账户是否激活")
    is_locked: bool = Field(..., description="账户是否被锁定")
    locked_until: Optional[datetime] = Field(None, description="锁定截止时间")
    login_attempts: int = Field(0, description="登录失败尝试次数")


class PasswordStrengthResponse(BaseModel):
    """密码强度响应模型"""
    score: int = Field(..., description="强度分数0-100")
    level: str = Field(..., description="强度等级：weak/medium/strong/very_strong")
    suggestions: list = Field(default_factory=list, description="改进建议")