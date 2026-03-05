# -*- coding: utf-8 -*-
"""
根据本机机器码签发 License Key（仅供授权方使用，需保管好私钥）。
用法:
  pip install PyJWT cryptography
  设置环境变量 OPENCLAW_LICENSE_PRIVATE_KEY 为私钥 PEM 内容，或把私钥保存为 private_key.pem 放在当前目录
  python scripts/generate_license_key.py [机器码] [有效期天数，默认365]
示例:
  python scripts/generate_license_key.py A1B2C3D4E5F6... 365
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_private_key_pem():
    pem = os.environ.get("OPENCLAW_LICENSE_PRIVATE_KEY")
    if pem:
        return pem
    path = os.path.join(os.path.dirname(__file__), "private_key.pem")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    print("错误: 请设置 OPENCLAW_LICENSE_PRIVATE_KEY 或放置 private_key.pem", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("用法: python generate_license_key.py <机器码> [有效期天数]", file=sys.stderr)
        print("机器码由用户在本机运行 openclaw-deploy --machine-id 获得。", file=sys.stderr)
        sys.exit(1)

    machine_id = sys.argv[1].strip().upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 365

    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    pem = get_private_key_pem()
    private_key = serialization.load_pem_private_key(
        pem.encode("utf-8"),
        password=None,
        backend=default_backend(),
    )

    payload = {
        "mid": machine_id,
        "exp": int(time.time()) + days * 86400,
        "iat": int(time.time()),
        "iss": "openclaw-deploy-tool",
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    if hasattr(token, "decode"):
        token = token.decode("utf-8")
    print("License Key（请交给用户，仅可在对应机器上使用）:")
    print(token)


if __name__ == "__main__":
    main()
