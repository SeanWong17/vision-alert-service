"""告警配置桥接模块：复用 core.settings 中的定义。"""

from app.core.settings import AlertSettings, load_alert_settings

__all__ = ["AlertSettings", "load_alert_settings"]
