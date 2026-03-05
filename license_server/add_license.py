# -*- coding: utf-8 -*-
"""
向授权服务数据文件中添加一个预置的 License Key（含有效期）。
与 app.py 使用同一 DATA_FILE，需在服务未运行或支持热加载时使用。
用法:
  python -m license_server.add_license [--expires "2026-12-31 23:59:59"] [--key "自定义Key"]
  不传 --key 则自动生成 UUID。
"""

import argparse
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("OPENCLAW_LICENSE_DATA", os.path.dirname(__file__)))
DATA_FILE = DATA_DIR / "licenses.json"


def main():
    parser = argparse.ArgumentParser(description="添加预置 License Key（含有效期）")
    parser.add_argument("--key", "-k", help="指定 License Key，不传则生成 UUID")
    parser.add_argument("--expires", "-e", default="2026-12-31 23:59:59", help="过期时间，默认 2026-12-31 23:59:59")
    args = parser.parse_args()

    license_key = (args.key or str(uuid.uuid4()).replace("-", "").upper()[:32]).strip()
    if not license_key:
        license_key = str(uuid.uuid4()).replace("-", "").upper()[:32]

    try:
        exp_dt = datetime.strptime(args.expires.strip(), "%Y-%m-%d %H:%M:%S")
        expires_at = exp_dt.isoformat()
    except ValueError:
        expires_at = args.expires.strip()

    if not DATA_FILE.exists():
        data = {"licenses": {}, "bindings": {}}
    else:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    if license_key in data.get("licenses", {}):
        print(f"Key 已存在: {license_key}")
        return 1

    data.setdefault("licenses", {})[license_key] = {"expires_at": expires_at}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已添加 License Key（有效期至 {expires_at}）:")
    print(license_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
