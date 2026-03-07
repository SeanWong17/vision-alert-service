"""配置中心模块：定义配置模型、加载器与告警运行参数。

配置来源优先级（高 -> 低）：
1. 环境变量（部署时临时覆盖）
2. runtime/config.json（长期配置）
3. 代码默认值（兜底）
"""

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


class AlertConfig(BaseModel):
    """告警业务配置（可由配置文件统一管理）。"""

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
    image_retention_days: int = 30
    cleanup_scan_interval_seconds: int = 3600
    default_limit: int = 1
    roi_default: tuple[int, int, int, int] = (-1, -1, -1, -1)
    near_water_distance_px: int = 24
    in_water_overlap_ratio: float = 0.08
    worker_poll_seconds: float = 0.05
    worker_threads: int = 4


class LicenseConfig(BaseModel):
    """授权校验配置。"""

    enabled: bool = False
    license_path: str = op.join(APP_HOME, "license", "license.json")
    public_key_path: str = op.join(APP_HOME, "license", "public_key.pem")
    fail_open: bool = False
    require_machine_binding: bool = True


class AppConfig(BaseModel):
    """顶层配置模型。"""

    redis: RedisSettings = RedisSettings()
    filepath: FileSettings = FileSettings()
    server: ServerSettings = ServerSettings()
    alert: AlertConfig = AlertConfig()
    license: LicenseConfig = LicenseConfig()


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
            # 配置文件损坏时回退默认，避免服务直接不可启动。
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
    image_retention_days: int = 30
    cleanup_scan_interval_seconds: int = 3600
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


@dataclass
class LicenseSettings:
    """运行时 license 校验配置。"""

    enabled: bool
    license_path: str
    public_key_path: str
    fail_open: bool = False
    require_machine_binding: bool = True


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

    alert_cfg = settings.alert
    model_root = _resolve_latest_model_root(settings.filepath.model_root)
    # 这里把“配置文件值 + 环境变量覆盖”统一折叠到运行时 dataclass，避免业务层关心来源。
    return AlertSettings(
        upload_root=settings.filepath.upload,
        result_root=settings.filepath.result,
        model_root=model_root,
        det_model_name=alert_cfg.det_model_name,
        seg_model_name=alert_cfg.seg_model_name,
        seg_config_name=alert_cfg.seg_config_name,
        detector_imgsz=tuple(alert_cfg.detector_imgsz),
        detector_conf=float(alert_cfg.detector_conf),
        detector_iou=float(alert_cfg.detector_iou),
        detector_device=os.getenv("ALERT_DET_DEVICE", alert_cfg.detector_device),
        segmentor_device=os.getenv("ALERT_SEG_DEVICE", alert_cfg.segmentor_device),
        queue_name=alert_cfg.queue_name,
        pending_key_prefix=alert_cfg.pending_key_prefix,
        result_key_prefix=alert_cfg.result_key_prefix,
        result_stream_prefix=alert_cfg.result_stream_prefix,
        result_ack_prefix=alert_cfg.result_ack_prefix,
        result_group_prefix=alert_cfg.result_group_prefix,
        result_claim_idle_ms=max(1000, int(os.getenv("ALERT_RESULT_CLAIM_IDLE_MS", str(alert_cfg.result_claim_idle_ms)))),
        upload_max_bytes=max(1024 * 1024, int(os.getenv("ALERT_UPLOAD_MAX_BYTES", str(alert_cfg.upload_max_bytes)))),
        allowed_image_types=tuple(alert_cfg.allowed_image_types),
        image_retention_days=max(1, int(os.getenv("ALERT_IMAGE_RETENTION_DAYS", str(alert_cfg.image_retention_days)))),
        cleanup_scan_interval_seconds=max(
            60,
            int(os.getenv("ALERT_CLEANUP_SCAN_INTERVAL_SECONDS", str(alert_cfg.cleanup_scan_interval_seconds))),
        ),
        default_limit=max(0, int(alert_cfg.default_limit)),
        roi_default=tuple(alert_cfg.roi_default),
        near_water_distance_px=max(0, int(alert_cfg.near_water_distance_px)),
        in_water_overlap_ratio=float(alert_cfg.in_water_overlap_ratio),
        worker_poll_seconds=max(0.01, float(alert_cfg.worker_poll_seconds)),
        worker_threads=max(1, int(os.getenv("ALERT_WORKER_THREADS", str(alert_cfg.worker_threads)))),
    )


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量。"""

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_license_settings() -> LicenseSettings:
    """从配置文件与环境变量加载授权校验参数。"""

    license_cfg = settings.license
    return LicenseSettings(
        enabled=_env_bool("ALERT_LICENSE_ENABLED", bool(license_cfg.enabled)),
        license_path=os.getenv("ALERT_LICENSE_PATH", license_cfg.license_path),
        public_key_path=os.getenv("ALERT_LICENSE_PUBLIC_KEY_PATH", license_cfg.public_key_path),
        fail_open=_env_bool("ALERT_LICENSE_FAIL_OPEN", bool(license_cfg.fail_open)),
        require_machine_binding=_env_bool(
            "ALERT_LICENSE_REQUIRE_MACHINE_BINDING",
            bool(license_cfg.require_machine_binding),
        ),
    )
