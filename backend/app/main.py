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

# 运行数据库迁移和创建表
try:
    import subprocess
    import os
    
    # 尝试运行Alembic迁移
    logger.info("运行数据库迁移...")
    
    # 尝试不同的工作目录
    possible_dirs = ["/app", "/app/backend", ".", "./backend", "../"]
    migration_success = False
    
    for work_dir in possible_dirs:
        try:
            if os.path.exists(work_dir):
                logger.info(f"尝试在目录 {work_dir} 运行迁移")
                # 首先尝试标记数据库为当前状态，然后运行增量迁移
                logger.info(f"在 {work_dir} 检查迁移状态")
                
                # 先尝试标记基础迁移为已完成
                stamp_result = subprocess.run(
                    ["alembic", "stamp", "7445f3b0d307"], 
                    cwd=work_dir,
                    capture_output=True, 
                    text=True
                )
                
                if stamp_result.returncode == 0:
                    logger.info("成功标记基础迁移为已完成")
                
                # 然后运行增量迁移
                result = subprocess.run(
                    ["alembic", "upgrade", "head"], 
                    cwd=work_dir,
                    capture_output=True, 
                    text=True
                )
                if result.returncode == 0:
                    logger.info(f"数据库迁移成功 (在 {work_dir})")
                    migration_success = True
                    break
                else:
                    logger.warning(f"在 {work_dir} 迁移失败: {result.stderr}")
        except Exception as e:
            logger.warning(f"在 {work_dir} 迁移出错: {e}")
            continue
    
    if not migration_success:
        logger.error("所有路径的迁移都失败了")
        # 如果迁移失败，使用create_all作为后备
        logger.info("使用create_all作为后备方案")
        Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"迁移过程出错: {e}")
    # 使用create_all作为后备
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