"""配置中心（app.common.settings）单元测试。

覆盖范围：
- ConfigLoader：加载默认配置、加载 JSON 文件、严格/宽松模式行为、单例重置
- AppConfig 及子模型：默认值正确性
- load_alert_settings：从配置文件加载、环境变量覆盖
- _resolve_latest_model_root：自动选择最大版本号子目录
- _env_bool：布尔环境变量解析
"""

import json
import os
import tempfile
import unittest
from unittest import mock


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全（需要 pydantic）。"""
    try:
        import pydantic  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), "pydantic not installed")
class TestEnvBool(unittest.TestCase):
    """测试 _env_bool 布尔环境变量解析函数。"""

    def _call(self, name: str, default: bool) -> bool:
        """快捷调用被测函数。"""
        from app.common.settings import _env_bool
        return _env_bool(name, default)

    def test_returns_default_when_env_not_set(self):
        """环境变量不存在时应返回默认值。"""
        env = {k: v for k, v in os.environ.items() if k != "_TEST_ENV_BOOL_MISSING"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(self._call("_TEST_ENV_BOOL_MISSING", True))
            self.assertFalse(self._call("_TEST_ENV_BOOL_MISSING", False))

    def test_truthy_values(self):
        """'1', 'true', 'yes', 'on'（含大小写和空格）应解析为 True。"""
        for val in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON", " true ", " 1 "):
            with mock.patch.dict(os.environ, {"_TEST_EB": val}):
                self.assertTrue(self._call("_TEST_EB", False), f"应为 True: {val!r}")

    def test_falsy_values(self):
        """'0', 'false', 'no', 'off' 等应解析为 False。"""
        for val in ("0", "false", "False", "no", "off", "whatever", ""):
            with mock.patch.dict(os.environ, {"_TEST_EB": val}):
                self.assertFalse(self._call("_TEST_EB", True), f"应为 False: {val!r}")


@unittest.skipUnless(_runtime_ready(), "pydantic not installed")
class TestResolveLatestModelRoot(unittest.TestCase):
    """测试 _resolve_latest_model_root 版本目录选择逻辑。"""

    def _call(self, base_dir: str) -> str:
        """快捷调用被测函数。"""
        from app.common.settings import _resolve_latest_model_root
        return _resolve_latest_model_root(base_dir)

    def test_nonexistent_dir_returns_itself(self):
        """目录不存在时应直接返回原路径。"""
        path = "/tmp/_non_existent_dir_test_settings_xyz"
        self.assertEqual(self._call(path), path)

    def test_empty_dir_returns_itself(self):
        """目录为空时应返回原路径。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(self._call(tmpdir), tmpdir)

    def test_no_numeric_subdirs_returns_itself(self):
        """只有非数字子目录时应返回原路径。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "abc"))
            os.makedirs(os.path.join(tmpdir, "config"))
            self.assertEqual(self._call(tmpdir), tmpdir)

    def test_selects_max_version(self):
        """存在多个数字子目录时应选择最大版本号。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            for v in ("1", "3", "10", "2"):
                os.makedirs(os.path.join(tmpdir, v))
            result = self._call(tmpdir)
            self.assertEqual(result, os.path.join(tmpdir, "10"))

    def test_mixed_dirs_ignores_non_numeric(self):
        """混合子目录时应忽略非数字名称，只看数字。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("5", "latest", "20", "backup"):
                os.makedirs(os.path.join(tmpdir, name))
            self.assertEqual(self._call(tmpdir), os.path.join(tmpdir, "20"))

    def test_single_version(self):
        """只有一个数字子目录时应返回该目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "42"))
            self.assertEqual(self._call(tmpdir), os.path.join(tmpdir, "42"))

    def test_preserves_zero_padded_version_name(self):
        """零填充版本目录应保留原始目录名，避免丢失前导 0。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "000001"))
            os.makedirs(os.path.join(tmpdir, "000010"))
            self.assertEqual(self._call(tmpdir), os.path.join(tmpdir, "000010"))


@unittest.skipUnless(_runtime_ready(), "pydantic not installed")
class TestAppConfigDefaults(unittest.TestCase):
    """测试 AppConfig 及子模型的默认值正确性。"""

    def test_redis_defaults(self):
        """RedisSettings 默认值应符合预期。"""
        from app.common.settings import RedisSettings
        r = RedisSettings()
        self.assertEqual(r.host, "127.0.0.1")
        self.assertEqual(r.port, 6379)
        self.assertEqual(r.database, 6)
        self.assertIsNone(r.password)

    def test_server_defaults(self):
        """ServerSettings 默认值应符合预期。"""
        from app.common.settings import ServerSettings
        s = ServerSettings()
        self.assertEqual(s.host, "0.0.0.0")
        self.assertEqual(s.port, 8011)

    def test_file_settings_properties(self):
        """FileSettings 的衍生路径属性应基于 root 拼接。"""
        from app.common.settings import FileSettings
        f = FileSettings(root="/test_root")
        self.assertEqual(f.upload, os.path.join("/test_root", "images/upload"))
        self.assertEqual(f.result, os.path.join("/test_root", "images/result"))
        self.assertEqual(f.log, os.path.join("/test_root", "log"))
        self.assertEqual(f.model_root, os.path.join("/test_root", "models"))

    def test_alert_config_defaults(self):
        """AlertConfig 关键默认值应符合预期。"""
        from app.common.settings import AlertConfig
        a = AlertConfig()
        self.assertEqual(a.det_model_name, "det_model.pt")
        self.assertEqual(a.seg_model_name, "seg_model.pt")
        self.assertEqual(a.detector_imgsz, (1280, 1280))
        self.assertAlmostEqual(a.detector_conf, 0.4)
        self.assertAlmostEqual(a.detector_iou, 0.45)
        self.assertEqual(a.detector_device, "0")
        self.assertEqual(a.segmentor_device, "cuda:0")
        self.assertEqual(a.worker_threads, 4)
        self.assertEqual(a.upload_max_bytes, 20 * 1024 * 1024)

    def test_app_config_contains_all_sections(self):
        """AppConfig 应包含全部子配置区段。"""
        from app.common.settings import AppConfig
        cfg = AppConfig()
        self.assertIsNotNone(cfg.redis)
        self.assertIsNotNone(cfg.filepath)
        self.assertIsNotNone(cfg.server)
        self.assertIsNotNone(cfg.alert)


@unittest.skipUnless(_runtime_ready(), "pydantic not installed")
class TestConfigLoader(unittest.TestCase):
    """测试 ConfigLoader 的加载、缓存、重置行为。"""

    def setUp(self):
        """每个测试前重置类级别单例缓存。"""
        from app.common.settings import ConfigLoader
        ConfigLoader._config = None

    def tearDown(self):
        """每个测试后重置类级别单例缓存，避免影响其他测试。"""
        from app.common.settings import ConfigLoader
        ConfigLoader._config = None

    def test_load_default_when_file_missing(self):
        """配置文件不存在时应加载默认配置。"""
        from app.common.settings import ConfigLoader
        loader = ConfigLoader(path="/tmp/_nonexistent_config_12345.json")
        cfg = loader.config
        self.assertEqual(cfg.server.port, 8011)
        self.assertEqual(cfg.redis.host, "127.0.0.1")

    def test_load_valid_json(self):
        """应能正确加载合法的 JSON 配置文件。"""
        from app.common.settings import ConfigLoader
        data = {
            "redis": {"host": "10.0.0.1", "port": 6380},
            "server": {"port": 9999},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(data, fp)
            fp.flush()
            tmp_path = fp.name
        try:
            loader = ConfigLoader(path=tmp_path)
            cfg = loader.config
            self.assertEqual(cfg.redis.host, "10.0.0.1")
            self.assertEqual(cfg.redis.port, 6380)
            self.assertEqual(cfg.server.port, 9999)
            # 未指定的字段应保持默认
            self.assertEqual(cfg.redis.database, 6)
        finally:
            os.unlink(tmp_path)

    def test_load_partial_json(self):
        """只包含部分配置的 JSON 文件，缺失字段应回退默认值。"""
        from app.common.settings import ConfigLoader
        data = {"alert": {"worker_threads": 8}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(data, fp)
            fp.flush()
            tmp_path = fp.name
        try:
            loader = ConfigLoader(path=tmp_path)
            cfg = loader.config
            self.assertEqual(cfg.alert.worker_threads, 8)
            # 其余保持默认
            self.assertEqual(cfg.server.port, 8011)
            self.assertEqual(cfg.redis.host, "127.0.0.1")
        finally:
            os.unlink(tmp_path)

    def test_strict_mode_raises_on_invalid_json(self):
        """严格模式下，非法 JSON 文件应抛出 ConfigLoadError。"""
        from app.common.settings import ConfigLoadError, ConfigLoader
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            fp.write("{invalid json content!!!")
            fp.flush()
            tmp_path = fp.name
        try:
            with mock.patch.dict(os.environ, {"ALERT_CONFIG_STRICT": "true"}):
                with self.assertRaises(ConfigLoadError):
                    ConfigLoader(path=tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_lenient_mode_falls_back_on_invalid_json(self):
        """宽松模式下，非法 JSON 文件应回退到默认配置。"""
        from app.common.settings import ConfigLoader
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            fp.write("NOT VALID JSON")
            fp.flush()
            tmp_path = fp.name
        try:
            with mock.patch.dict(os.environ, {"ALERT_CONFIG_STRICT": "false"}):
                loader = ConfigLoader(path=tmp_path)
                cfg = loader.config
                self.assertEqual(cfg.server.port, 8011)
        finally:
            os.unlink(tmp_path)

    def test_reset_restores_defaults(self):
        """reset() 应将缓存配置恢复为默认值。"""
        from app.common.settings import ConfigLoader
        data = {"server": {"port": 7777}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(data, fp)
            fp.flush()
            tmp_path = fp.name
        try:
            loader = ConfigLoader(path=tmp_path)
            self.assertEqual(loader.config.server.port, 7777)
            loader.reset()
            self.assertEqual(loader.config.server.port, 8011)
        finally:
            os.unlink(tmp_path)

    def test_reload_reloads_from_disk(self):
        """reload() 应从磁盘重新读取配置。"""
        from app.common.settings import ConfigLoader
        data = {"server": {"port": 5555}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(data, fp)
            fp.flush()
            tmp_path = fp.name
        try:
            loader = ConfigLoader(path=tmp_path)
            self.assertEqual(loader.config.server.port, 5555)

            # 修改磁盘上的配置文件
            with open(tmp_path, "w", encoding="utf-8") as fp2:
                json.dump({"server": {"port": 6666}}, fp2)

            loader.reload()
            self.assertEqual(loader.config.server.port, 6666)
        finally:
            os.unlink(tmp_path)

    def test_save_writes_json(self):
        """save() 应将当前配置写入 JSON 文件。"""
        from app.common.settings import ConfigLoader
        ConfigLoader._config = None
        loader = ConfigLoader(path="/tmp/_nonexistent_placeholder.json")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "saved_config.json")
            loader.save(path=out_path)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "r", encoding="utf-8") as fp:
                saved = json.load(fp)
            self.assertIn("redis", saved)
            self.assertIn("server", saved)
            self.assertEqual(saved["server"]["port"], 8011)

    def test_singleton_behavior(self):
        """多次实例化 ConfigLoader 应共享同一份配置（单例）。"""
        from app.common.settings import ConfigLoader
        loader1 = ConfigLoader(path="/tmp/_nonexistent_1.json")
        loader2 = ConfigLoader(path="/tmp/_nonexistent_2.json")
        # 两个实例应返回同一份配置对象
        self.assertIs(loader1.config, loader2.config)


@unittest.skipUnless(_runtime_ready(), "pydantic not installed")
class TestLoadAlertSettings(unittest.TestCase):
    """测试 load_alert_settings 函数。"""

    def setUp(self):
        """重置 ConfigLoader 单例并准备临时配置文件。"""
        from app.common.settings import ConfigLoader
        ConfigLoader._config = None

    def tearDown(self):
        """还原 ConfigLoader 单例。"""
        from app.common.settings import ConfigLoader
        ConfigLoader._config = None

    def test_loads_from_config_defaults(self):
        """无配置文件、无环境变量时应使用默认值。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        # 加载一个不存在的配置路径 -> 全默认
        loader = ConfigLoader(path="/tmp/_alert_settings_test_no_file.json")
        # 替换模块级 settings 引用为我们的默认配置
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            result = mod.load_alert_settings()
            self.assertEqual(result.detector_device, "0")
            self.assertEqual(result.segmentor_device, "cuda:0")
            self.assertEqual(result.worker_threads, 4)
            self.assertEqual(result.worker_max_inflight, 64)
            self.assertEqual(result.det_model_name, "det_model.pt")
            self.assertEqual(result.upload_max_bytes, 20 * 1024 * 1024)
        finally:
            mod.settings = original_settings

    def test_env_overrides_det_device(self):
        """ALERT_DET_DEVICE 环境变量应覆盖 detector_device。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        loader = ConfigLoader(path="/tmp/_alert_env_test.json")
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            with mock.patch.dict(os.environ, {"ALERT_DET_DEVICE": "cpu"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.detector_device, "cpu")
        finally:
            mod.settings = original_settings

    def test_env_overrides_seg_device(self):
        """ALERT_SEG_DEVICE 环境变量应覆盖 segmentor_device。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        loader = ConfigLoader(path="/tmp/_alert_env_test.json")
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            with mock.patch.dict(os.environ, {"ALERT_SEG_DEVICE": "cuda:1"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.segmentor_device, "cuda:1")
        finally:
            mod.settings = original_settings

    def test_env_overrides_worker_threads(self):
        """ALERT_WORKER_THREADS 环境变量应覆盖 worker_threads。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        loader = ConfigLoader(path="/tmp/_alert_env_test.json")
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            with mock.patch.dict(os.environ, {"ALERT_WORKER_THREADS": "16"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.worker_threads, 16)
        finally:
            mod.settings = original_settings

    def test_env_overrides_worker_max_inflight(self):
        """ALERT_WORKER_MAX_INFLIGHT 环境变量应覆盖 worker_max_inflight。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        loader = ConfigLoader(path="/tmp/_alert_env_test.json")
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            with mock.patch.dict(os.environ, {"ALERT_WORKER_MAX_INFLIGHT": "128"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.worker_max_inflight, 128)
        finally:
            mod.settings = original_settings

    def test_env_overrides_dead_letter_queue(self):
        """ALERT_DEAD_LETTER_QUEUE 环境变量应覆盖 dead_letter_queue。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        loader = ConfigLoader(path="/tmp/_alert_env_test.json")
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            with mock.patch.dict(os.environ, {"ALERT_DEAD_LETTER_QUEUE": "custom:dlq"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.dead_letter_queue, "custom:dlq")
        finally:
            mod.settings = original_settings

    def test_env_overrides_upload_max_bytes_with_min_clamp(self):
        """ALERT_UPLOAD_MAX_BYTES 应被下限钳位到 1MB。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        loader = ConfigLoader(path="/tmp/_alert_env_test.json")
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            # 设一个低于下限的值
            with mock.patch.dict(os.environ, {"ALERT_UPLOAD_MAX_BYTES": "100"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.upload_max_bytes, 1024 * 1024)
        finally:
            mod.settings = original_settings

    def test_env_overrides_image_retention_days(self):
        """ALERT_IMAGE_RETENTION_DAYS 环境变量应覆盖且下限钳位到 1。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        loader = ConfigLoader(path="/tmp/_alert_env_test.json")
        original_settings = mod.settings
        try:
            mod.settings = loader.config
            with mock.patch.dict(os.environ, {"ALERT_IMAGE_RETENTION_DAYS": "7"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.image_retention_days, 7)
            # 测试下限钳位
            with mock.patch.dict(os.environ, {"ALERT_IMAGE_RETENTION_DAYS": "0"}):
                result = mod.load_alert_settings()
                self.assertEqual(result.image_retention_days, 1)
        finally:
            mod.settings = original_settings

    def test_loads_from_json_config(self):
        """应能从 JSON 配置文件中加载 alert 参数。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        data = {
            "alert": {
                "worker_threads": 12,
                "detector_device": "cpu",
                "detector_conf": 0.6,
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(data, fp)
            fp.flush()
            tmp_path = fp.name
        try:
            loader = ConfigLoader(path=tmp_path)
            original_settings = mod.settings
            try:
                mod.settings = loader.config
                result = mod.load_alert_settings()
                self.assertEqual(result.worker_threads, 12)
                self.assertEqual(result.detector_device, "cpu")
                self.assertAlmostEqual(result.detector_conf, 0.6)
            finally:
                mod.settings = original_settings
        finally:
            os.unlink(tmp_path)

    def test_loads_legacy_segmentor_water_class_ids_alias(self):
        """兼容旧配置字段 segmentor_water_class_ids。"""
        import app.common.settings as mod
        from app.common.settings import ConfigLoader

        data = {
            "alert": {
                "segmentor_water_class_ids": [21],
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(data, fp)
            fp.flush()
            tmp_path = fp.name
        try:
            loader = ConfigLoader(path=tmp_path)
            original_settings = mod.settings
            try:
                mod.settings = loader.config
                result = mod.load_alert_settings()
                self.assertEqual(result.segmentor_target_class_ids, (21,))
            finally:
                mod.settings = original_settings
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
