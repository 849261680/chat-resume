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

# 从环境变量获取CORS配置
cors_origins = settings.BACKEND_CORS_ORIGINS
logger.info(f"CORS Origins from settings: {cors_origins}")
logger.info(f"CORS Origins type: {type(cors_origins)}")

# 如果是生产环境且配置了特定域名，使用特定域名；否则允许所有来源
if cors_origins and len(cors_origins) > 0 and cors_origins != ["http://localhost:3000,https://localhost:3000"]:
    logger.info("Using specific CORS origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
else:
    logger.info("Using wildcard CORS origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
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

# 移除手动OPTIONS处理，让CORS中间件自动处理