"""API 包入口：导出根路由并加载具体路由模块。"""

from fastapi import APIRouter

# 根路由对象，供应用工厂统一挂载。
router = APIRouter()

# 导入路由定义模块以触发注册。
from app.api import routes  # noqa: E402,F401
