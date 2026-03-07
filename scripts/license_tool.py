"""License 生成与签名工具（Ed25519）。

用途：
1) 生成密钥对：私钥用于签发，公钥用于服务端校验
2) 生成带签名的 license.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _canonical_payload(payload: dict) -> bytes:
    """与服务端一致的签名原文序列化方式。"""

    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return text.encode("utf-8")


def cmd_gen_key(args) -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    os.makedirs(os.path.dirname(args.private_key), exist_ok=True)
    os.makedirs(os.path.dirname(args.public_key), exist_ok=True)

    with open(args.private_key, "wb") as fp:
        fp.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(args.public_key, "wb") as fp:
        fp.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    print(f"generated private key: {args.private_key}")
    print(f"generated public key: {args.public_key}")


def cmd_sign(args) -> None:
    """签发 license：把声明字段签名后写入 signature。"""

    with open(args.private_key, "rb") as fp:
        private_key = serialization.load_pem_private_key(fp.read(), password=None)

    payload = {
        "subject": args.subject,
        "issuedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "expiresAt": args.expires_at,
        "machineId": args.machine_id,
    }
    signature = private_key.sign(_canonical_payload(payload))
    payload["signature"] = base64.b64encode(signature).decode("ascii")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
        fp.write("\n")
    print(f"generated license: {args.output}")


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("gen-key")
    p1.add_argument("--private-key", required=True)
    p1.add_argument("--public-key", required=True)
    p1.set_defaults(func=cmd_gen_key)

    p2 = sub.add_parser("sign")
    p2.add_argument("--private-key", required=True)
    p2.add_argument("--subject", required=True)
    p2.add_argument("--machine-id", required=True)
    p2.add_argument("--expires-at", required=True, help="ISO8601, e.g. 2027-12-31T23:59:59Z")
    p2.add_argument("--output", required=True)
    p2.set_defaults(func=cmd_sign)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
