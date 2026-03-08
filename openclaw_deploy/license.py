# -*- coding: utf-8 -*-
"""
License 校验：用户输入 License Key 后，将本机 machine_id 上传至服务器激活/验证。
一个 License Key 只能绑定一台机器，服务器验证通过后用户才能继续一键部署。
"""

import os
import sys
import urllib.request
import urllib.error
import json
from typing import Optional, Tuple

from loguru import logger

# 授权服务器地址，可通过环境变量 OPENCLAW_LICENSE_SERVER 覆盖
DEFAULT_LICENSE_SERVER_URL = os.environ.get("OPENCLAW_LICENSE_SERVER", "http://8.134.83.168:8090")


def _ensure_utf8_stdout():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def get_license_server_url() -> str:
    """获取授权服务器根 URL（无末尾斜杠）。"""
    url = os.environ.get("OPENCLAW_LICENSE_SERVER", DEFAULT_LICENSE_SERVER_URL).strip().rstrip("/")
    return url


def activate_and_verify(
    license_key: str,
    machine_id: str,
    server_base_url: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    向服务器提交 License Key 与当前机器码，完成激活或验证。
    - 若 Key 未绑定：绑定到本机，返回成功。
    - 若已绑定本机：验证通过，返回成功。
    - 若已绑定其他机器：返回失败。
    服务器验证通过后，用户才能继续一键部署。
    """
    _ensure_utf8_stdout()
    key_clean = license_key.replace(" ", "").replace("\n", "").strip()
    if not key_clean:
        return False, "License Key 不能为空"
    if not machine_id:
        return False, "机器码为空"

    base = (server_base_url or get_license_server_url()).rstrip("/")
    url = f"{base}/api/activate"
    body = json.dumps({"license_key": key_clean, "machine_id": machine_id}).encode("utf-8")
    logger.info("请求授权服务器: {} (machine_id 已包含在请求中)", base)

    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            try:
                out = json.loads(data) if data else {}
            except json.JSONDecodeError:
                out = {}
            if out.get("ok") is True:
                logger.info("服务器验证通过")
                return True, None
            msg = out.get("message") or "服务器返回异常"
            logger.warning("服务器拒绝: {}", msg)
            return False, msg
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            out = json.loads(body) if body else {}
            msg = out.get("message") or e.reason or str(e.code)
        except Exception:
            msg = e.reason or str(e.code)
        logger.warning("授权服务器 HTTP 错误 {}: {}", e.code, msg)
        return False, msg
    except urllib.error.URLError as e:
        logger.warning("无法连接授权服务器: {}", e.reason)
        return False, f"无法连接授权服务器: {e.reason}"
    except Exception as e:
        logger.exception("验证请求失败")
        return False, f"验证请求失败: {e}"


def save_license_to_file(license_key: str, path: Optional[str] = None) -> bool:
    """将校验通过的 License 写入本地文件，下次无需重复输入。"""
    if path is None:
        path = os.path.join(os.path.expanduser("~"), ".openclaw_deploy_license")
    try:
        dirpath = os.path.dirname(path)
        if dirpath and not os.path.isdir(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(license_key.replace(" ", "").strip())
        return True
    except Exception:
        return False


def load_license_from_file(path: Optional[str] = None) -> Optional[str]:
    """从本地文件读取已保存的 License。"""
    if path is None:
        path = os.path.join(os.path.expanduser("~"), ".openclaw_deploy_license")
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return None
