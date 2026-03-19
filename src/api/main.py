"""
FastAPI 主应用

该模块是 FastAPI 应用的入口点，包含应用配置、
中间件、异常处理器等。
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import VMManagerError
from src.api.routers import vms

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时初始化资源，关闭时清理资源
    """
    # 启动时
    logger.info("Starting VM Manager API...")
    logger.info(f"Application started: {app.title} v{app.version}")

    yield

    # 关闭时
    logger.info("Shutting down VM Manager API...")


# 创建 FastAPI 应用
app = FastAPI(
    title="天工 (TianGong) API",
    description="基于 Qemu/KVM 的虚拟机生命周期管理 API",
    version="0.1.0",
    contact={
        "name": "John Young",
        "email": "john.young@foxmai.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 自定义异常处理器
@app.exception_handler(VMManagerError)
async def vm_manager_exception_handler(request: Request, exc: VMManagerError):
    """
    处理自定义虚拟机管理异常
    """
    logger.error(f"VMManagerError: {exc}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": exc.__class__.__name__,
                "message": str(exc),
                "type": "vm_manager_error",
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    处理请求验证异常
    """
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求数据验证失败",
                "details": exc.errors(),
                "type": "validation_error",
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    处理 HTTP 异常
    """
    logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "status_code": exc.status_code,
                "type": "http_error",
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    处理未捕获的异常
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误",
                "type": "internal_error",
            }
        },
    )


# 健康检查端点
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    健康检查端点

    返回应用状态信息
    """
    return {
        "status": "healthy",
        "service": "天工 (TianGong) API",
        "version": app.version,
        "timestamp": "2024-01-01T00:00:00Z",  # 实际应使用当前时间
    }


@app.get("/", tags=["root"])
async def root() -> Dict[str, Any]:
    """
    根端点

    返回 API 基本信息
    """
    return {
        "message": "Welcome to 天工 (TianGong) API",
        "version": app.version,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/api/v1/openapi.json",
    }


# 注册路由
app.include_router(vms.router, prefix="/api/v1", tags=["virtual-machines"])


# 中间件：记录请求日志
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    记录 HTTP 请求日志
    """
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


# 中间件：添加安全头
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    添加安全相关的 HTTP 头
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )