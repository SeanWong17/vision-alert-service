"""ASGI 入口模块。"""

from app.application import create_app

# 供 uvicorn/gunicorn 直接加载的应用对象。
app = create_app()
