# -*- coding: utf-8 -*-
"""
License 授权服务：预置有效 License Key（含有效期），用户输入 Key 后上传 machine_id 激活。
一个 License Key 只能绑定一台机器，绑定后仅该机器可验证通过。
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple

from loguru import logger

# 数据文件：licenses 列表 + bindings 映射
DATA_DIR = Path(os.environ.get("OPENCLAW_LICENSE_DATA", os.path.dirname(__file__)))
DATA_FILE = DATA_DIR / "licenses.json"


def _init_server_logger():
    """初始化服务端日志：控制台 + 日志目录下的 app.log。"""
    import sys
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_dir / "app.log"),
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )


def _load_data():
    if not DATA_FILE.exists():
        return {"licenses": {}, "bindings": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"licenses": {}, "bindings": {}}


def _save_data(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def activate(license_key: str, machine_id: str) -> Tuple[bool, str]:
    """
    激活或验证：若 Key 有效且未过期，
    - 未绑定则绑定到本机并返回成功；
    - 已绑定本机则返回成功；
    - 已绑定其他机器则返回失败。
    """
    key = license_key.strip()
    mid = (machine_id or "").strip()
    if not key or not mid:
        return False, "参数不能为空"

    data = _load_data()
    licenses = data.get("licenses", {})
    bindings = data.get("bindings", {})

    if key not in licenses:
        logger.warning("无效 License Key: {}", key[:8] + "...")
        return False, "License Key 无效"

    info = licenses[key]
    expires_at = info.get("expires_at")
    if expires_at:
        try:
            if isinstance(expires_at, (int, float)):
                exp_dt = datetime.utcfromtimestamp(expires_at)
            else:
                s = str(expires_at)[:19].replace("T", " ")
                exp_dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            if datetime.now() >= exp_dt:
                return False, "License 已过期"
        except Exception:
            return False, "License 已过期"

    current_binding = bindings.get(key)
    if current_binding is None:
        bindings[key] = mid
        data["bindings"] = bindings
        _save_data(data)
        logger.info("License 激活成功 key={} machine_id={}", key[:8] + "...", mid[:16] + "...")
        return True, "激活成功，已绑定本机"
    if current_binding == mid:
        logger.debug("License 验证通过 key={} machine_id={}", key[:8] + "...", mid[:16] + "...")
        return True, "验证通过，已绑定本机"
    logger.warning("License 已绑定其他设备 key={} 当前请求 machine_id={}", key[:8] + "...", mid[:16] + "...")
    return False, "此 License 已绑定到其他设备，一台设备只能绑定一个 Key"


def create_app():
    from flask import Flask, request, jsonify

    app = Flask(__name__)

    @app.route("/api/activate", methods=["POST"])
    def api_activate():
        try:
            body = request.get_json() or {}
            license_key = body.get("license_key", "")
            machine_id = body.get("machine_id", "")
        except Exception as e:
            logger.warning("请求体解析失败: {}", e)
            return jsonify({"ok": False, "message": "请求体格式错误"}), 400
        ok, message = activate(license_key, machine_id)
        if ok:
            return jsonify({"ok": True, "message": message})
        return jsonify({"ok": False, "message": message}), 403

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"ok": True})

    return app


def run_server(host="0.0.0.0", port=8080, debug=False):
    _init_server_logger()
    logger.info("License 授权服务启动 {}:{}", host, port)
    app = create_app()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    run_server(host=args.host, port=args.port, debug=args.debug)
