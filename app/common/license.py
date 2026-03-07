"""License 校验模块：签名、有效期、机器绑定。"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.common.settings import LicenseSettings


class LicenseError(RuntimeError):
    """授权校验失败。"""


@dataclass
class LicenseClaims:
    """License 声明字段。"""

    subject: str
    issued_at: datetime
    expires_at: datetime
    machine_id: str = ""


def _parse_iso8601(value: str) -> datetime:
    """解析 ISO8601 时间，兼容结尾 Z。"""

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_machine_id() -> str:
    """读取本机标识。"""

    candidates = ["/etc/machine-id", "/var/lib/dbus/machine-id"]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    value = fp.read().strip()
                if value:
                    return value
            except Exception:
                continue
    return os.getenv("HOSTNAME", "").strip()


def _load_license_file(path: str) -> Dict[str, Any]:
    """读取 license JSON。"""

    if not os.path.exists(path):
        raise LicenseError(f"license file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception as exc:
        raise LicenseError(f"invalid license file: {exc}") from exc
    if not isinstance(data, dict):
        raise LicenseError("license payload must be a json object")
    return data


def _load_public_key(path: str) -> Ed25519PublicKey:
    """加载 PEM 公钥。"""

    if not os.path.exists(path):
        raise LicenseError(f"public key file not found: {path}")
    try:
        with open(path, "rb") as fp:
            key_data = fp.read()
        key = serialization.load_pem_public_key(key_data)
    except Exception as exc:
        raise LicenseError(f"invalid public key: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseError("public key must be an Ed25519 key")
    return key


def _canonical_payload(data: Dict[str, Any]) -> bytes:
    """序列化签名原文（去掉 signature 字段）。"""

    payload = dict(data)
    payload.pop("signature", None)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return text.encode("utf-8")


def _parse_claims(data: Dict[str, Any]) -> LicenseClaims:
    """解析并校验 license 核心字段。"""

    try:
        subject = str(data["subject"])
        issued_at = _parse_iso8601(str(data["issuedAt"]))
        expires_at = _parse_iso8601(str(data["expiresAt"]))
    except KeyError as exc:
        raise LicenseError(f"missing required claim: {exc}") from exc
    except Exception as exc:
        raise LicenseError(f"invalid claim format: {exc}") from exc

    if expires_at <= issued_at:
        raise LicenseError("expiresAt must be later than issuedAt")
    return LicenseClaims(subject=subject, issued_at=issued_at, expires_at=expires_at, machine_id=str(data.get("machineId", "")))


def validate_license(settings: LicenseSettings) -> LicenseClaims:
    """校验 license，并返回解析后的声明。"""

    data = _load_license_file(settings.license_path)
    claims = _parse_claims(data)

    signature_b64 = data.get("signature")
    if not signature_b64:
        raise LicenseError("license signature is required")

    try:
        signature = base64.b64decode(str(signature_b64), validate=True)
    except Exception as exc:
        raise LicenseError(f"invalid signature encoding: {exc}") from exc

    public_key = _load_public_key(settings.public_key_path)
    try:
        public_key.verify(signature, _canonical_payload(data))
    except InvalidSignature as exc:
        raise LicenseError("license signature verification failed") from exc

    now = datetime.now(timezone.utc)
    if now >= claims.expires_at:
        raise LicenseError(f"license expired at {claims.expires_at.isoformat()}")

    if settings.require_machine_binding:
        current_machine = _read_machine_id()
        if not current_machine:
            raise LicenseError("cannot read machine id")
        if not claims.machine_id:
            raise LicenseError("license does not include machineId")
        if claims.machine_id != current_machine:
            raise LicenseError("license machineId does not match current device")

    return claims
