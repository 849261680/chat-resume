"""
API路由聚合模块

负责聚合和注册所有API端点路由。
提供统一的API入口点管理。
"""

from fastapi import APIRouter

from app.entrypoints.http import (
    auth,
    billing,
    digital_human,
    export,
    interviews,
    resumes,
    upload,
    users,
)
from app.entrypoints.http import (
    resume_agent as chat,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(export.router, prefix="/resumes", tags=["export"])
api_router.include_router(chat.router, prefix="/ai", tags=["chat"])
api_router.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
api_router.include_router(
    digital_human.router, prefix="/digital-human", tags=["digital-human"]
)
