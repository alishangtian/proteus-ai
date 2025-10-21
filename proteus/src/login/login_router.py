from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from passlib.context import CryptContext
import os, logging, redis, uuid, time, json
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()


class RedisManager:
    def __init__(self):
        self._pool = None
        self._client = None
        self.max_retries = 3
        self.retry_delay = 1
        self._connect()

    def _connect(self):
        for attempt in range(self.max_retries):
            try:
                self._pool = redis.ConnectionPool(
                    host=os.getenv("REDIS_HOST"),
                    port=int(os.getenv("REDIS_PORT")),
                    db=int(os.getenv("REDIS_DB")),
                    password=os.getenv("REDIS_PASSWORD"),
                    decode_responses=True,
                    health_check_interval=30,
                    socket_keepalive=True,
                    max_connections=20,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
                self._client = redis.Redis(connection_pool=self._pool)
                # 测试连接是否可用
                self._client.ping()
                return
            except (redis.ConnectionError, redis.TimeoutError) as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(
                    f"Redis连接失败，尝试重连({attempt + 1}/{self.max_retries}): {e}"
                )
                time.sleep(self.retry_delay)

    def get_client(self):
        try:
            # 检查连接是否活跃
            self._client.ping()
            return self._client
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis连接丢失，尝试重新连接...")
            self._connect()
            return self._client


redis_manager = RedisManager()
redis_client = redis_manager.get_client()


class FileStorageManager:
    """本地文件存储管理器"""

    def __init__(self):
        self.data_dir = os.getenv("DATA_PATH", "./data")
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_user_file(self, username: str) -> str:
        return os.path.join(self.data_dir, f"user_{username}.json")

    def _get_session_file(self, session_id: str) -> str:
        return os.path.join(self.data_dir, f"session_{session_id}.json")

    def save_user(self, username: str, user_data: dict):
        """保存用户数据到文件"""
        try:
            with open(self._get_user_file(username), "w") as f:
                json.dump(user_data, f)
            return True
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
            return False

    def get_user(self, username: str) -> Optional[dict]:
        """从文件获取用户数据"""
        try:
            with open(self._get_user_file(username), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"读取用户数据失败: {e}")
            return None

    def save_session(self, session_id: str, session_data: dict):
        """保存会话数据到文件"""
        try:
            with open(self._get_session_file(session_id), "w") as f:
                json.dump(session_data, f)
            return True
        except Exception as e:
            logger.error(f"保存会话数据失败: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[dict]:
        """从文件获取会话数据"""
        try:
            with open(self._get_session_file(session_id), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"读取会话数据失败: {e}")
            return None

    def delete_session(self, session_id: str):
        """删除会话文件"""
        try:
            os.remove(self._get_session_file(session_id))
            return True
        except FileNotFoundError:
            return True
        except Exception as e:
            logger.error(f"删除会话文件失败: {e}")
            return False


file_storage = FileStorageManager()
SESSION_MODEL = os.getenv("SESSION_MODEL", "redis")

router = APIRouter(tags=["认证模块"])

# 密码哈希配置
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # 明确指定rounds参数
    bcrypt__ident="2b",  # 使用现代bcrypt标识
)

# 会话配置
SESSION_EXPIRE_MINUTES = int(os.getenv("SESSION_EXPIRE_MINUTES", 30))
SESSION_PREFIX = "session:"
USER_PREFIX = "user:"


def get_session_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def get_user_key(username: str) -> str:
    return f"{USER_PREFIX}{username}"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "password" in values and v != values["password"]:
            raise ValueError("密码不一致")
        return v


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6)


class SessionData(BaseModel):
    username: str
    expires: str  # 存储为ISO格式字符串

    @classmethod
    def create(cls, username: str, expires: datetime):
        return cls(username=username, expires=expires.isoformat())


class ApiResponse(BaseModel):
    event: str = Field(..., description="事件类型")
    success: bool = Field(..., description="操作是否成功")
    data: Optional[dict] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")


async def get_current_user(request: Request) -> Optional[SessionData]:
    """获取当前登录用户"""
    session_id = request.cookies.get("session")
    if not session_id:
        return None

    if SESSION_MODEL == "redis":
        session_key = get_session_key(session_id)
        try:
            session_data = redis_client.hgetall(session_key)
            if not session_data:
                return None
        except redis.RedisError as e:
            logger.error(f"获取会话数据失败: {e}")
            return None
    else:
        session_data = file_storage.get_session(session_id)
        if not session_data:
            return None
    logger.info(f"获取会话数据成功: {session_data}")

    return SessionData(
        username=session_data["username"], expires=session_data["expires"]
    )


def verify_password(plain_password: str, hashed_password: str):
    """验证密码"""
    try:
        # 确保明文密码和哈希密码都是字符串类型
        if isinstance(plain_password, bytes):
            plain_password = plain_password.decode("utf-8")
        if isinstance(hashed_password, bytes):
            hashed_password = hashed_password.decode("utf-8")
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"密码验证失败: {e}")
        return False


def get_password_hash(password: str):
    """生成密码哈希"""
    try:
        # 确保密码是字符串类型，bcrypt会在内部处理编码
        if isinstance(password, bytes):
            password = password.decode("utf-8")
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"密码哈希生成失败: {e}")
        raise


@router.post("/register", response_model=ApiResponse)
async def register(register_data: RegisterRequest):
    """用户注册接口"""
    user_data = {
        "username": register_data.username,
        "email": register_data.email,
        "hashed_password": get_password_hash(register_data.password),
        "disabled": "False",
    }

    if SESSION_MODEL == "redis":
        user_key = get_user_key(register_data.username)
        try:
            if redis_client.exists(user_key):
                return ApiResponse(
                    event="register", success=False, error="用户名已存在"
                ).dict()
            redis_client.hmset(user_key, user_data)
        except redis.RedisError as e:
            logger.error(f"用户注册操作失败: {e}")
            return ApiResponse(
                event="register", success=False, error="系统错误，请稍后重试"
            ).dict()
    else:
        if file_storage.get_user(register_data.username):
            return ApiResponse(
                event="register", success=False, error="用户名已存在"
            ).dict()
        if not file_storage.save_user(register_data.username, user_data):
            return ApiResponse(
                event="register", success=False, error="系统错误，请稍后重试"
            ).dict()

    return ApiResponse(
        event="register", success=True, data={"username": register_data.username}
    ).dict()


@router.post("/login", response_model=ApiResponse)
async def login(request: Request, login_data: LoginRequest):
    """用户登录接口"""
    logger.info(f"login info {login_data.username}:{login_data.password}")

    if SESSION_MODEL == "redis":
        user_key = get_user_key(login_data.username)
        try:
            user_data = redis_client.hgetall(user_key)
        except redis.RedisError as e:
            logger.error(f"用户登录操作失败: {e}")
            return ApiResponse(
                event="login", success=False, error="系统错误，请稍后重试"
            ).dict()
    else:
        user_data = file_storage.get_user(login_data.username)

    if not user_data or not verify_password(
        login_data.password, user_data["hashed_password"]
    ):
        return ApiResponse(
            event="login", success=False, error="无效的用户名或密码"
        ).dict()

    session_id = str(uuid.uuid4())
    expires = datetime.now() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
    session_data = {"username": login_data.username, "expires": expires.isoformat()}

    if SESSION_MODEL == "redis":
        session_key = get_session_key(session_id)
        try:
            redis_client.hmset(session_key, session_data)
            redis_client.expire(session_key, SESSION_EXPIRE_MINUTES * 60)
        except redis.RedisError as e:
            logger.error(f"用户登录操作失败: {e}")
            return ApiResponse(
                event="login", success=False, error="系统错误，请稍后重试"
            ).dict()
    else:
        if not file_storage.save_session(session_id, session_data):
            return ApiResponse(
                event="login", success=False, error="系统错误，请稍后重试"
            ).dict()

    response = JSONResponse(content=ApiResponse(event="login", success=True).dict())
    response.set_cookie(
        key="session",
        value=session_id,
        max_age=SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
    return response


@router.get("/register")
async def serve_register_page():
    """返回注册页面"""
    return FileResponse("static/register.html")


@router.get("/login")
async def serve_register_page():
    """返回注册页面"""
    return FileResponse("static/login.html")


@router.get("/logout", response_model=ApiResponse)
async def logout(request: Request):
    """用户登出接口"""
    session_id = request.cookies.get("session")
    if session_id:
        if SESSION_MODEL == "redis":
            session_key = get_session_key(session_id)
            try:
                redis_client.delete(session_key)
            except redis.RedisError as e:
                logger.error(f"删除会话失败: {e}")
        else:
            if not file_storage.delete_session(session_id):
                logger.error("删除会话文件失败")

    response = JSONResponse(content=ApiResponse(event="logout", success=True).dict())
    response.delete_cookie("session")
    return response


@router.get("/check_session", response_model=ApiResponse)
async def check_session(user: Optional[SessionData] = Depends(get_current_user)):
    """检查会话状态"""
    if user:
        return ApiResponse(
            event="check_session", success=True, data={"username": user.username}
        ).dict()
    return ApiResponse(event="check_session", success=False, error="未登录").dict()
