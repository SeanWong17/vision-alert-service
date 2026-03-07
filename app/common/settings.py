"""配置中心模块：定义配置模型、加载器与告警运行参数。"""

from __future__ import annotations

import json
import os
import os.path as op
from dataclasses import dataclass
from threading import Lock

from pydantic import BaseModel

HOME_PATH = op.expanduser("~")
APP_HOME = op.join(HOME_PATH, ".ai_alerting")
DEFAULT_CONFIG_PATH = op.join(APP_HOME, "config.json")


class RedisSettings(BaseModel):
    """Redis 连接配置。"""

    host: str = "127.0.0.1"
    port: int = 6379
    database: int = 6
    password: str | None = None


class FileSettings(BaseModel):
    """服务运行时使用的目录配置。"""

    root: str = APP_HOME

    @property
    def upload(self) -> str:
        """上传原图目录。"""
        return op.join(self.root, "images/upload")

    @property
    def result(self) -> str:
        """结果图目录。"""
        return op.join(self.root, "images/result")

    @property
    def log(self) -> str:
        """日志目录。"""
        return op.join(self.root, "log")

    @property
    def model_root(self) -> str:
        """模型根目录。"""
        return op.join(self.root, "models")


class ServerSettings(BaseModel):
    """HTTP 服务监听配置。"""

    host: str = "0.0.0.0"
    port: int = 8011


class AppConfig(BaseModel):
    """顶层配置模型。"""

    redis: RedisSettings = RedisSettings()
    filepath: FileSettings = FileSettings()
    server: ServerSettings = ServerSettings()


class ConfigLoader:
    """线程安全配置加载器：读取 JSON，失败时回退默认值。"""

    _lock = Lock()
    _config: AppConfig | None = None

    def __init__(self, path: str = DEFAULT_CONFIG_PATH):
        """初始化加载器并按需懒加载配置。"""
        self.path = path
        if ConfigLoader._config is None:
            with ConfigLoader._lock:
                if ConfigLoader._config is None:
                    ConfigLoader._config = self._load(path)

    def _load(self, path: str) -> AppConfig:
        """从指定路径读取配置文件。"""
        if not os.path.exists(path):
            return AppConfig()
        try:
            with open(path, "r", encoding="utf-8") as fp:
                return AppConfig(**json.load(fp))
        except Exception:
            return AppConfig()

    @property
    def config(self) -> AppConfig:
        """返回当前缓存配置。"""
        return ConfigLoader._config or AppConfig()

    def save(self, path: str | None = None) -> None:
        """将当前配置保存为 JSON 文件。"""
        target = path or self.path
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fp:
            json.dump(self.config.dict(), fp, indent=2, ensure_ascii=False)
            fp.write("\n")

    def reset(self) -> None:
        """重置配置为默认值。"""
        with ConfigLoader._lock:
            ConfigLoader._config = AppConfig()

    def reload(self, path: str | None = None) -> None:
        """从磁盘重新加载配置。"""
        with ConfigLoader._lock:
            ConfigLoader._config = self._load(path or self.path)


loader = ConfigLoader()
settings = loader.config


@dataclass
class AlertSettings:
    """告警领域运行参数。"""

    upload_root: str
    result_root: str
    model_root: str
    det_model_name: str = "det_model.pt"
    seg_model_name: str = "seg_model.pt"
    seg_config_name: str = "mmseg_config.py"
    detector_imgsz: tuple[int, int] = (1280, 1280)
    detector_conf: float = 0.4
    detector_iou: float = 0.45
    detector_device: str = "0"
    segmentor_device: str = "cuda:0"
    queue_name: str = "alert:queue:pending"
    pending_key_prefix: str = "alert:pending"
    result_key_prefix: str = "alert:result"
    result_stream_prefix: str = "alert:result_stream"
    result_ack_prefix: str = "alert:result_ack"
    result_group_prefix: str = "alert:result_group"
    result_claim_idle_ms: int = 60000
    upload_max_bytes: int = 20 * 1024 * 1024
    allowed_image_types: tuple[str, ...] = ("image/jpg", "image/jpeg", "image/png")
    default_limit: int = 1
    roi_default: tuple[int, int, int, int] = (-1, -1, -1, -1)
    near_water_distance_px: int = 24
    in_water_overlap_ratio: float = 0.08
    worker_poll_seconds: float = 0.05
    worker_threads: int = 4

    def pending_key(self, session_id: str) -> str:
        """生成 pending 哈希 key。"""
        return f"{self.pending_key_prefix}:{session_id}"

    def result_key(self, session_id: str) -> str:
        """生成 result 哈希 key。"""
        return f"{self.result_key_prefix}:{session_id}"

    def result_stream_key(self, session_id: str) -> str:
        """生成 result stream key。"""
        return f"{self.result_stream_prefix}:{session_id}"

    def result_ack_key(self, session_id: str) -> str:
        """生成 result ack 映射 key（imageId -> stream entry id）。"""
        return f"{self.result_ack_prefix}:{session_id}"

    def result_group(self, session_id: str) -> str:
        """生成 result stream consumer group 名称。"""
        return f"{self.result_group_prefix}:{session_id}"


def _resolve_latest_model_root(base_dir: str) -> str:
    """解析最新版本模型目录（取最大数字子目录）。"""
    if not os.path.isdir(base_dir):
        return base_dir
    versions = [int(name) for name in os.listdir(base_dir) if name.isdigit()]
    if not versions:
        return base_dir
    return os.path.join(base_dir, str(max(versions)))


def load_alert_settings() -> AlertSettings:
    """从全局配置与环境变量组合出告警参数。"""
    model_root = _resolve_latest_model_root(settings.filepath.model_root)
    return AlertSettings(
        upload_root=settings.filepath.upload,
        result_root=settings.filepath.result,
        model_root=model_root,
        detector_device=os.getenv("ALERT_DET_DEVICE", "0"),
        segmentor_device=os.getenv("ALERT_SEG_DEVICE", "cuda:0"),
        worker_threads=max(1, int(os.getenv("ALERT_WORKER_THREADS", "4"))),
        result_claim_idle_ms=max(1000, int(os.getenv("ALERT_RESULT_CLAIM_IDLE_MS", "60000"))),
        upload_max_bytes=max(1024 * 1024, int(os.getenv("ALERT_UPLOAD_MAX_BYTES", str(20 * 1024 * 1024)))),
    )
