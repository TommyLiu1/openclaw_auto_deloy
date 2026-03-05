# -*- coding: utf-8 -*-
"""
生成 License 签发用的 RSA 密钥对。
运行: pip install cryptography && python scripts/generate_license_keys.py
将输出的公钥替换到 openclaw_deploy/license.py 的 LICENSE_PUBLIC_KEY_PEM，
私钥妥善保管并用于 scripts/generate_license_key.py 签发 License。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def main():
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo(),
    ).decode("utf-8")

    print("=" * 60)
    print("将下面 PUBLIC KEY 复制到 openclaw_deploy/license.py 的 LICENSE_PUBLIC_KEY_PEM")
    print("=" * 60)
    print(pub_pem)
    print("=" * 60)
    print("将下面 PRIVATE KEY 保存到安全位置，用于 scripts/generate_license_key.py 签发")
    print("=" * 60)
    print(priv_pem)


if __name__ == "__main__":
    main()
