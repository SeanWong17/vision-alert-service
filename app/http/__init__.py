"""HTTP 接口包入口：导出根路由并加载具体路由模块。"""

from fastapi import APIRouter

router = APIRouter()

from app.http import routes  # noqa: E402,F401
