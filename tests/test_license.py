"""License 校验模块测试。"""

import base64
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization


def _runtime_ready() -> bool:
    """检测运行依赖是否齐全。"""

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: F811
        return True
    except Exception:
        return False


def _make_settings(**overrides):
    """构造测试用 LicenseSettings 实例。"""

    from app.common.settings import LicenseSettings

    defaults = dict(
        enabled=True,
        license_path="/tmp/test_license.json",
        public_key_path="/tmp/test_pub.pem",
        fail_open=False,
        require_machine_binding=False,
        allow_hostname_fallback=False,
        check_interval_seconds=300,
    )
    defaults.update(overrides)
    return LicenseSettings(**defaults)


def _generate_keypair():
    """生成 Ed25519 密钥对，返回 (private_key, public_key_pem_bytes)。"""

    private_key = Ed25519PrivateKey.generate()
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_key_pem


def _sign_payload(private_key: Ed25519PrivateKey, data: dict) -> str:
    """对 license 负载签名，返回 base64 编码的签名字符串。"""

    payload = dict(data)
    payload.pop("signature", None)
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    sig = private_key.sign(canonical)
    return base64.b64encode(sig).decode("ascii")


# ---------------------------------------------------------------------------
# 1. _parse_iso8601
# ---------------------------------------------------------------------------

@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class ParseISO8601Test(unittest.TestCase):
    """验证 ISO8601 时间解析逻辑。"""

    def _parse(self, value: str) -> datetime:
        from app.common.license import _parse_iso8601
        return _parse_iso8601(value)

    def test_z_suffix(self):
        """以 Z 结尾的时间应被正确解析为 UTC。"""

        result = self._parse("2026-06-01T12:00:00Z")
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.hour, 12)

    def test_with_timezone_offset(self):
        """带显式时区偏移的时间应被转换为 UTC。"""

        result = self._parse("2026-06-01T20:00:00+08:00")
        self.assertEqual(result.tzinfo, timezone.utc)
        # +08:00 的 20:00 等于 UTC 12:00
        self.assertEqual(result.hour, 12)

    def test_naive_datetime_treated_as_utc(self):
        """不带时区信息的时间应被视为 UTC。"""

        result = self._parse("2026-03-15T09:30:00")
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.hour, 9)
        self.assertEqual(result.minute, 30)

    def test_whitespace_is_stripped(self):
        """前后空白字符应被忽略。"""

        result = self._parse("  2026-01-01T00:00:00Z  ")
        self.assertEqual(result.year, 2026)

    def test_invalid_format_raises(self):
        """非法格式应抛出异常。"""

        with self.assertRaises(Exception):
            self._parse("not-a-date")


# ---------------------------------------------------------------------------
# 2. _canonical_payload
# ---------------------------------------------------------------------------

@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class CanonicalPayloadTest(unittest.TestCase):
    """验证签名原文序列化逻辑。"""

    def test_signature_field_is_excluded(self):
        """序列化结果应排除 signature 字段。"""

        from app.common.license import _canonical_payload

        data = {"b": 2, "a": 1, "signature": "xxx"}
        result = _canonical_payload(data)
        parsed = json.loads(result)
        self.assertNotIn("signature", parsed)

    def test_keys_are_sorted(self):
        """序列化键应按字典序排列。"""

        from app.common.license import _canonical_payload

        data = {"z": 1, "a": 2, "m": 3}
        result = _canonical_payload(data)
        # 紧凑格式、排序后应为 {"a":2,"m":3,"z":1}
        self.assertEqual(result, b'{"a":2,"m":3,"z":1}')

    def test_compact_separators(self):
        """序列化应使用紧凑分隔符（无多余空格）。"""

        from app.common.license import _canonical_payload

        data = {"key": "value"}
        result = _canonical_payload(data)
        self.assertNotIn(b" ", result)

    def test_original_dict_is_not_mutated(self):
        """原始字典不应被修改。"""

        from app.common.license import _canonical_payload

        data = {"a": 1, "signature": "keep"}
        _canonical_payload(data)
        self.assertIn("signature", data)

    def test_returns_bytes(self):
        """返回值应为 bytes 类型。"""

        from app.common.license import _canonical_payload

        result = _canonical_payload({"k": "v"})
        self.assertIsInstance(result, bytes)


# ---------------------------------------------------------------------------
# 3. _parse_claims
# ---------------------------------------------------------------------------

@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class ParseClaimsTest(unittest.TestCase):
    """验证声明字段解析与校验逻辑。"""

    def _parse(self, data: dict):
        from app.common.license import _parse_claims
        return _parse_claims(data)

    def test_valid_claims(self):
        """合法数据应被正确解析。"""

        claims = self._parse({
            "subject": "customer_a",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2027-01-01T00:00:00Z",
            "machineId": "abc123",
        })
        self.assertEqual(claims.subject, "customer_a")
        self.assertEqual(claims.machine_id, "abc123")
        self.assertTrue(claims.expires_at > claims.issued_at)

    def test_missing_subject_raises(self):
        """缺少 subject 字段应抛出 LicenseError。"""

        from app.common.license import LicenseError

        with self.assertRaises(LicenseError) as ctx:
            self._parse({
                "issuedAt": "2026-01-01T00:00:00Z",
                "expiresAt": "2027-01-01T00:00:00Z",
            })
        self.assertIn("missing required claim", str(ctx.exception))

    def test_missing_issued_at_raises(self):
        """缺少 issuedAt 字段应抛出 LicenseError。"""

        from app.common.license import LicenseError

        with self.assertRaises(LicenseError):
            self._parse({
                "subject": "x",
                "expiresAt": "2027-01-01T00:00:00Z",
            })

    def test_missing_expires_at_raises(self):
        """缺少 expiresAt 字段应抛出 LicenseError。"""

        from app.common.license import LicenseError

        with self.assertRaises(LicenseError):
            self._parse({
                "subject": "x",
                "issuedAt": "2026-01-01T00:00:00Z",
            })

    def test_expires_at_equal_to_issued_at_raises(self):
        """expiresAt 等于 issuedAt 应抛出 LicenseError。"""

        from app.common.license import LicenseError

        with self.assertRaises(LicenseError) as ctx:
            self._parse({
                "subject": "x",
                "issuedAt": "2026-01-01T00:00:00Z",
                "expiresAt": "2026-01-01T00:00:00Z",
            })
        self.assertIn("expiresAt must be later than issuedAt", str(ctx.exception))

    def test_expires_at_before_issued_at_raises(self):
        """expiresAt 早于 issuedAt 应抛出 LicenseError。"""

        from app.common.license import LicenseError

        with self.assertRaises(LicenseError):
            self._parse({
                "subject": "x",
                "issuedAt": "2027-01-01T00:00:00Z",
                "expiresAt": "2026-01-01T00:00:00Z",
            })

    def test_default_machine_id_is_empty(self):
        """未提供 machineId 时应默认为空字符串。"""

        claims = self._parse({
            "subject": "x",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2027-01-01T00:00:00Z",
        })
        self.assertEqual(claims.machine_id, "")


# ---------------------------------------------------------------------------
# 4. _load_license_file
# ---------------------------------------------------------------------------

@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class LoadLicenseFileTest(unittest.TestCase):
    """验证 license 文件加载逻辑。"""

    def test_file_not_found_raises(self):
        """文件不存在应抛出 LicenseError。"""

        from app.common.license import LicenseError, _load_license_file

        with self.assertRaises(LicenseError) as ctx:
            _load_license_file("/nonexistent/path/license.json")
        self.assertIn("not found", str(ctx.exception))

    def test_invalid_json_raises(self):
        """非法 JSON 内容应抛出 LicenseError。"""

        from app.common.license import LicenseError, _load_license_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fp:
            fp.write("{not valid json!!}")
            tmp_path = fp.name
        try:
            with self.assertRaises(LicenseError) as ctx:
                _load_license_file(tmp_path)
            self.assertIn("invalid license file", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_non_object_json_raises(self):
        """顶层不是 JSON 对象应抛出 LicenseError。"""

        from app.common.license import LicenseError, _load_license_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fp:
            json.dump([1, 2, 3], fp)
            tmp_path = fp.name
        try:
            with self.assertRaises(LicenseError) as ctx:
                _load_license_file(tmp_path)
            self.assertIn("json object", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_valid_json_is_loaded(self):
        """合法 JSON 文件应被正确加载。"""

        from app.common.license import _load_license_file

        data = {"subject": "test", "issuedAt": "2026-01-01T00:00:00Z"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fp:
            json.dump(data, fp)
            tmp_path = fp.name
        try:
            result = _load_license_file(tmp_path)
            self.assertEqual(result["subject"], "test")
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 5. _read_machine_id
# ---------------------------------------------------------------------------

@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class ReadMachineIdTest(unittest.TestCase):
    """验证机器标识读取逻辑。"""

    @patch("app.common.license.os.path.exists", return_value=True)
    @patch("builtins.open", create=True)
    def test_reads_from_etc_machine_id(self, mock_open, mock_exists):
        """应优先从 /etc/machine-id 读取。"""

        from app.common.license import _read_machine_id
        from unittest.mock import mock_open as _mock_open

        m = _mock_open(read_data="abc123def\n")
        mock_open.side_effect = m
        result = _read_machine_id()
        self.assertEqual(result, "abc123def")

    @patch("app.common.license.os.path.exists", return_value=False)
    def test_returns_empty_when_no_file(self, mock_exists):
        """无 machine-id 文件且未启用 hostname 兜底时应返回空字符串。"""

        from app.common.license import _read_machine_id

        result = _read_machine_id(allow_hostname_fallback=False)
        self.assertEqual(result, "")

    @patch("app.common.license.os.path.exists", return_value=False)
    @patch.dict(os.environ, {"HOSTNAME": "test-host-01"})
    def test_hostname_fallback(self, mock_exists):
        """启用 hostname 兜底时应从环境变量读取 HOSTNAME。"""

        from app.common.license import _read_machine_id

        result = _read_machine_id(allow_hostname_fallback=True)
        self.assertEqual(result, "test-host-01")

    @patch("app.common.license.os.path.exists", return_value=False)
    @patch.dict(os.environ, {}, clear=True)
    def test_hostname_fallback_empty_env(self, mock_exists):
        """HOSTNAME 环境变量为空时应返回空字符串。"""

        from app.common.license import _read_machine_id

        result = _read_machine_id(allow_hostname_fallback=True)
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# 6. LicenseGuard
# ---------------------------------------------------------------------------

@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class LicenseGuardTest(unittest.TestCase):
    """验证 LicenseGuard 运行期守卫行为。"""

    def _make_guard(self, **overrides):
        """构造 LicenseGuard 实例。"""

        from app.common.license import LicenseGuard
        return LicenseGuard(_make_settings(**overrides))

    @patch("app.common.license.validate_license")
    def test_fail_open_allows_on_error(self, mock_validate):
        """fail_open 模式下，校验失败仍应允许服务继续。"""

        from app.common.license import LicenseError

        mock_validate.side_effect = LicenseError("expired")
        guard = self._make_guard(fail_open=True)
        ok, err = guard.ensure_valid()
        self.assertTrue(ok)
        self.assertIsNotNone(err)
        self.assertIn("expired", err)

    @patch("app.common.license.validate_license")
    def test_fail_closed_blocks_on_error(self, mock_validate):
        """fail_open=False 时，校验失败应拒绝服务。"""

        from app.common.license import LicenseError

        mock_validate.side_effect = LicenseError("expired")
        guard = self._make_guard(fail_open=False)
        ok, err = guard.ensure_valid()
        self.assertFalse(ok)
        self.assertIn("expired", err)

    @patch("app.common.license.validate_license")
    def test_check_interval_caching(self, mock_validate):
        """在 check_interval 内重复调用不应再次校验。"""

        from app.common.license import LicenseClaims

        mock_validate.return_value = LicenseClaims(
            subject="x",
            issued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        guard = self._make_guard(check_interval_seconds=3600)
        guard.ensure_valid()
        guard.ensure_valid()
        guard.ensure_valid()
        # 应只调用一次 validate_license
        self.assertEqual(mock_validate.call_count, 1)

    @patch("app.common.license.validate_license")
    def test_force_bypasses_cache(self, mock_validate):
        """force=True 应绕过缓存、重新校验。"""

        from app.common.license import LicenseClaims

        mock_validate.return_value = LicenseClaims(
            subject="x",
            issued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        guard = self._make_guard(check_interval_seconds=3600)
        guard.ensure_valid()
        guard.ensure_valid(force=True)
        self.assertEqual(mock_validate.call_count, 2)

    @patch("app.common.license.validate_license")
    def test_successful_validation_clears_error(self, mock_validate):
        """校验成功后应清除上次的错误信息。"""

        from app.common.license import LicenseClaims, LicenseError

        # 第一次失败
        mock_validate.side_effect = LicenseError("first error")
        guard = self._make_guard(fail_open=True, check_interval_seconds=0)
        ok1, err1 = guard.ensure_valid()
        self.assertTrue(ok1)
        self.assertIsNotNone(err1)

        # 第二次成功
        mock_validate.side_effect = None
        mock_validate.return_value = LicenseClaims(
            subject="x",
            issued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        ok2, err2 = guard.ensure_valid(force=True)
        self.assertTrue(ok2)
        self.assertIsNone(err2)

    @patch("app.common.license.validate_license")
    def test_cached_error_blocks_in_fail_closed(self, mock_validate):
        """fail_open=False 时，缓存期内上次的错误应继续阻断服务。"""

        from app.common.license import LicenseError

        mock_validate.side_effect = LicenseError("bad license")
        guard = self._make_guard(fail_open=False, check_interval_seconds=3600)
        guard.ensure_valid()

        # 第二次调用命中缓存，应仍然返回失败
        ok, err = guard.ensure_valid()
        self.assertFalse(ok)
        self.assertIn("bad license", err)

    @patch("app.common.license.validate_license")
    def test_cached_error_allows_in_fail_open(self, mock_validate):
        """fail_open=True 时，缓存期内上次的错误应允许继续但携带错误信息。"""

        from app.common.license import LicenseError

        mock_validate.side_effect = LicenseError("bad license")
        guard = self._make_guard(fail_open=True, check_interval_seconds=3600)
        guard.ensure_valid()

        # 第二次调用命中缓存，fail_open 模式应仍然放行
        ok, err = guard.ensure_valid()
        self.assertTrue(ok)
        self.assertIn("bad license", err)


# ---------------------------------------------------------------------------
# 7. validate_license（完整流程）
# ---------------------------------------------------------------------------

@unittest.skipUnless(_runtime_ready(), "runtime deps not installed")
class ValidateLicenseTest(unittest.TestCase):
    """验证完整的 license 校验流程（包含签名验证）。"""

    def setUp(self):
        """创建临时密钥对和 license 文件。"""

        self._tmpdir = tempfile.mkdtemp()
        self._private_key, self._pub_pem = _generate_keypair()
        self._pub_path = os.path.join(self._tmpdir, "public_key.pem")
        with open(self._pub_path, "wb") as fp:
            fp.write(self._pub_pem)
        self._license_path = os.path.join(self._tmpdir, "license.json")

    def tearDown(self):
        """清理临时文件。"""

        for name in os.listdir(self._tmpdir):
            os.unlink(os.path.join(self._tmpdir, name))
        os.rmdir(self._tmpdir)

    def _write_license(self, data: dict) -> None:
        """将 license 数据写入临时文件（自动签名）。"""

        sig = _sign_payload(self._private_key, data)
        data["signature"] = sig
        with open(self._license_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp)

    def test_valid_license_passes(self):
        """合法 license（签名正确、未过期）应通过校验。"""

        from app.common.license import validate_license

        self._write_license({
            "subject": "customer_test",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
            "machineId": "m1",
        })
        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=False,
        )
        claims = validate_license(settings)
        self.assertEqual(claims.subject, "customer_test")
        self.assertEqual(claims.machine_id, "m1")

    def test_expired_license_raises(self):
        """已过期的 license 应抛出 LicenseError。"""

        from app.common.license import LicenseError, validate_license

        self._write_license({
            "subject": "customer_test",
            "issuedAt": "2020-01-01T00:00:00Z",
            "expiresAt": "2021-01-01T00:00:00Z",
        })
        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=False,
        )
        with self.assertRaises(LicenseError) as ctx:
            validate_license(settings)
        self.assertIn("expired", str(ctx.exception))

    def test_tampered_signature_raises(self):
        """签名被篡改应抛出 LicenseError。"""

        from app.common.license import LicenseError, validate_license

        self._write_license({
            "subject": "customer_test",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
        })
        # 篡改 license 文件中的签名
        with open(self._license_path, "r") as fp:
            data = json.load(fp)
        # 用随机合法 base64 替换签名
        data["signature"] = base64.b64encode(b"x" * 64).decode()
        with open(self._license_path, "w") as fp:
            json.dump(data, fp)

        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=False,
        )
        with self.assertRaises(LicenseError) as ctx:
            validate_license(settings)
        self.assertIn("signature verification failed", str(ctx.exception))

    def test_missing_signature_raises(self):
        """缺少签名字段应抛出 LicenseError。"""

        from app.common.license import LicenseError, validate_license

        data = {
            "subject": "customer_test",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
        }
        with open(self._license_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp)

        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=False,
        )
        with self.assertRaises(LicenseError) as ctx:
            validate_license(settings)
        self.assertIn("signature is required", str(ctx.exception))

    @patch("app.common.license._read_machine_id", return_value="machine-abc")
    def test_machine_binding_match(self, mock_mid):
        """machineId 匹配当前设备时应通过。"""

        from app.common.license import validate_license

        self._write_license({
            "subject": "customer_test",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
            "machineId": "machine-abc",
        })
        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=True,
        )
        claims = validate_license(settings)
        self.assertEqual(claims.subject, "customer_test")

    @patch("app.common.license._read_machine_id", return_value="machine-abc")
    def test_machine_binding_mismatch_raises(self, mock_mid):
        """machineId 不匹配时应抛出 LicenseError。"""

        from app.common.license import LicenseError, validate_license

        self._write_license({
            "subject": "customer_test",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
            "machineId": "other-machine",
        })
        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=True,
        )
        with self.assertRaises(LicenseError) as ctx:
            validate_license(settings)
        self.assertIn("does not match", str(ctx.exception))

    @patch("app.common.license._read_machine_id", return_value="")
    def test_machine_binding_no_machine_id_raises(self, mock_mid):
        """读取不到本机标识时应抛出 LicenseError。"""

        from app.common.license import LicenseError, validate_license

        self._write_license({
            "subject": "customer_test",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
            "machineId": "some-machine",
        })
        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=True,
        )
        with self.assertRaises(LicenseError) as ctx:
            validate_license(settings)
        self.assertIn("cannot read machine id", str(ctx.exception))

    def test_invalid_signature_encoding_raises(self):
        """signature 字段 base64 解码失败应抛出 LicenseError。"""

        from app.common.license import LicenseError, validate_license

        data = {
            "subject": "customer_test",
            "issuedAt": "2026-01-01T00:00:00Z",
            "expiresAt": "2099-01-01T00:00:00Z",
            "signature": "!!!not-valid-base64!!!",
        }
        with open(self._license_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp)

        settings = _make_settings(
            license_path=self._license_path,
            public_key_path=self._pub_path,
            require_machine_binding=False,
        )
        with self.assertRaises(LicenseError) as ctx:
            validate_license(settings)
        self.assertIn("invalid signature encoding", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
