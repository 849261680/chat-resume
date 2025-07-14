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

# 简化CORS配置 - 临时允许所有来源进行调试
logger.info("Setting up CORS with allow all origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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

# 添加通用的OPTIONS处理
@app.options("/{path:path}")
async def options_handler(path: str):
    return {"message": f"OPTIONS allowed for {path}"}