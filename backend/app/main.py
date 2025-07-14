from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import api_router
from app.core.database import engine, Base
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 添加中间件来记录请求
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 获取CORS配置
cors_origins = ["*"]  # 临时允许所有域名
if hasattr(settings, 'BACKEND_CORS_ORIGINS'):
    cors_origins = settings.BACKEND_CORS_ORIGINS

logger.info(f"CORS Origins: {cors_origins}")

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Chat Resume API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/v1/test")
async def test_endpoint():
    return {"message": "API is working", "cors": "enabled"}

@app.options("/api/v1/auth/register")
async def register_options():
    return {"message": "OPTIONS allowed"}

@app.options("/api/v1/auth/login")
async def login_options():
    return {"message": "OPTIONS allowed"}