# -*- coding: utf-8 -*-
"""
OpenClaw 一键部署：优先 Docker，其次本机 Node.js。
支持 Windows / Mac / Linux。
可选：根据用户提供的配置文件配置 QQ、钉钉、企业微信、飞书等通道，并校验配置是否成功。
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
from typing import Optional, Tuple

from loguru import logger

from . import channels_config as ch_cfg


def _ensure_utf8():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _run(cmd: list, timeout: int = 120, shell: bool = False) -> Tuple[bool, str]:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and not shell else 0,
        )
        out = (r.stdout or "").strip() + "\n" + (r.stderr or "").strip()
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "执行超时"
    except Exception as e:
        return False, str(e)


def has_docker() -> bool:
    ok, _ = _run(["docker", "info"])
    return ok


def has_node22() -> bool:
    ok, out = _run(["node", "-v"])
    if not ok:
        return False
    try:
        # v22.x.x -> 22
        ver = out.strip().replace("v", "").split(".")[0]
        return int(ver) >= 22
    except Exception:
        return False


def deploy_with_docker() -> Tuple[bool, str]:
    """使用 Docker 部署 OpenClaw。"""
    _ensure_utf8()
    logger.info("检测到 Docker，使用 Docker 方式部署")
    ok, out = _run(["docker", "pull", "openclaw/openclaw:latest"], timeout=300)
    if not ok:
        logger.error("拉取镜像失败: {}", out)
        return False, f"拉取镜像失败: {out}"

    # 若已存在同名容器则先停止并删除（便于重复部署）
    _run(["docker", "stop", "openclaw"], timeout=30)
    _run(["docker", "rm", "openclaw"], timeout=10)

    cmd = [
        "docker", "run", "-d",
        "--name", "openclaw",
        "--restart", "unless-stopped",
        "-p", "127.0.0.1:18789:18789",
        "-v", "openclaw-data:/root/.openclaw",
        "--cap-drop", "ALL",
        "--cap-add", "NET_BIND_SERVICE",
        "--security-opt", "no-new-privileges:true",
        "openclaw/openclaw:latest",
    ]
    ok, out = _run(cmd, timeout=60)
    if not ok:
        logger.error("启动容器失败: {}", out)
        return False, f"启动容器失败: {out}"
    logger.info("Docker 容器已启动")
    return True, "Docker 部署成功。管理界面: http://127.0.0.1:18789/ ，请在容器内执行: docker exec -it openclaw openclaw onboard"


def _apply_channels_config_docker(user_config_path: str) -> Tuple[bool, str]:
    """在 Docker 容器内应用用户通道配置并重启网关。"""
    try:
        user_channels = ch_cfg.load_and_normalize_user_channels(user_config_path)
    except FileNotFoundError as e:
        return False, str(e)
    except json.JSONDecodeError as e:
        return False, f"配置文件不是合法 JSON: {e}"
    if not user_channels:
        return True, "配置文件中无支持的通道（feishu/wecom/dingtalk/qq），已跳过"
    # 从容器读取当前 openclaw.json
    ok, out = _run(["docker", "exec", "openclaw", "cat", "/root/.openclaw/openclaw.json"], timeout=10)
    if not ok or not out.strip():
        current = {}
    else:
        try:
            current = json.loads(out)
        except json.JSONDecodeError:
            current = {}
    merged = ch_cfg.merge_channels_into_openclaw(current, user_channels)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        tmp = f.name
    try:
        ok, out = _run(["docker", "cp", tmp, "openclaw:/root/.openclaw/openclaw.json"], timeout=10)
        if not ok:
            return False, f"写入容器配置失败: {out}"
        ok, out = _run(["docker", "exec", "openclaw", "openclaw", "gateway", "restart"], timeout=30)
        if not ok:
            logger.warning("网关重启命令返回: {}", out)
        return True, "通道配置已写入并已尝试重启网关"
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def _apply_channels_config_node(user_config_path: str) -> Tuple[bool, str]:
    """在本机 Node 部署下应用用户通道配置并重启网关。"""
    try:
        user_channels = ch_cfg.load_and_normalize_user_channels(user_config_path)
    except FileNotFoundError as e:
        return False, str(e)
    except json.JSONDecodeError as e:
        return False, f"配置文件不是合法 JSON: {e}"
    if not user_channels:
        return True, "配置文件中无支持的通道，已跳过"
    openclaw_dir = os.path.expanduser("~/.openclaw")
    config_path = os.path.join(openclaw_dir, "openclaw.json")
    if os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            current = json.load(f)
    else:
        current = {}
    merged = ch_cfg.merge_channels_into_openclaw(current, user_channels)
    os.makedirs(openclaw_dir, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    ok, out = _run(["openclaw", "gateway", "restart"], timeout=30)
    if not ok:
        logger.warning("网关重启返回: {}", out)
    return True, "通道配置已写入并已尝试重启网关"


def _verify_channels_config_docker(user_config_path: str) -> Tuple[bool, str]:
    """校验 Docker 容器内通道配置是否生效。"""
    try:
        user_channels = ch_cfg.load_and_normalize_user_channels(user_config_path)
    except Exception:
        return True, "未使用通道配置或解析失败，跳过校验"
    if not user_channels:
        return True, "无通道需校验"
    ok, out = _run(["docker", "exec", "openclaw", "cat", "/root/.openclaw/openclaw.json"], timeout=10)
    if not ok:
        return False, "无法读取容器内 openclaw.json"
    try:
        current = json.loads(out)
    except json.JSONDecodeError:
        return False, "容器内 openclaw.json 格式错误"
    passed, errors = ch_cfg.verify_channels_in_openclaw(current, user_channels)
    if passed:
        return True, "通道配置校验通过"
    return False, "配置校验未通过: " + "; ".join(errors)


def _verify_channels_config_node(user_config_path: str) -> Tuple[bool, str]:
    """校验本机 Node 部署下通道配置是否生效。"""
    try:
        user_channels = ch_cfg.load_and_normalize_user_channels(user_config_path)
    except Exception:
        return True, "未使用通道配置或解析失败，跳过校验"
    if not user_channels:
        return True, "无通道需校验"
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.isfile(config_path):
        return False, "未找到 ~/.openclaw/openclaw.json"
    with open(config_path, "r", encoding="utf-8") as f:
        current = json.load(f)
    passed, errors = ch_cfg.verify_channels_in_openclaw(current, user_channels)
    if passed:
        return True, "通道配置校验通过"
    return False, "配置校验未通过: " + "; ".join(errors)


def apply_and_verify_channels_config(
    user_config_path: str,
    use_docker: bool,
) -> Tuple[bool, str]:
    """应用用户通道配置并校验是否成功。"""
    if use_docker:
        ok, msg = _apply_channels_config_docker(user_config_path)
    else:
        ok, msg = _apply_channels_config_node(user_config_path)
    if not ok:
        return False, msg
    logger.info("应用配置: {}", msg)
    if use_docker:
        ok, msg = _verify_channels_config_docker(user_config_path)
    else:
        ok, msg = _verify_channels_config_node(user_config_path)
    if not ok:
        return False, msg
    logger.info("校验配置: {}", msg)
    return True, msg


def deploy_with_node() -> Tuple[bool, str]:
    """本机 Node.js 安装 OpenClaw（适用于 Linux / Mac，Windows 建议用 Docker）。"""
    _ensure_utf8()
    logger.info("使用 Node 方式部署")
    system = platform.system().lower()
    if system == "windows":
        return False, "Windows 建议使用 Docker 部署。请安装 Docker Desktop 后重新运行。"

    ok, out = _run(["npm", "install", "-g", "openclaw@latest"], timeout=300)
    if not ok:
        logger.error("npm 安装失败: {}", out)
        return False, f"npm 安装失败: {out}"

    ok, out = _run(["openclaw", "onboard", "--install-daemon"], timeout=120)
    if not ok:
        logger.error("openclaw onboard 失败: {}", out)
        return False, f"openclaw onboard 失败: {out}"
    logger.info("Node 方式部署完成")
    return True, "Node 方式部署成功。请使用 openclaw 命令管理服务，管理端口 18789。"


def run_deploy(config_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    一键部署：优先 Docker，否则尝试 Node（仅 Linux/Mac）。
    若提供 config_path，部署完成后会根据配置文件配置 QQ/钉钉/企业微信/飞书等通道并校验。
    """
    _ensure_utf8()
    use_docker = has_docker()
    if use_docker:
        logger.debug("已检测到 Docker")
        ok, msg = deploy_with_docker()
    elif has_node22():
        logger.debug("已检测到 Node.js 22+")
        ok, msg = deploy_with_node()
    else:
        logger.warning("未检测到 Docker 或 Node.js 22+")
        return False, (
            "未检测到 Docker 或 Node.js 22+。\n"
            "请先安装其一：\n"
            "  - Docker: https://docs.docker.com/get-docker/\n"
            "  - Node.js 22+: https://nodejs.org/"
        )
    if not ok:
        return False, msg
    if config_path and os.path.isfile(config_path):
        ok2, msg2 = apply_and_verify_channels_config(config_path, use_docker)
        if not ok2:
            return False, msg2
        msg = msg + "\n通道配置已应用并校验通过。"
    elif config_path:
        logger.warning("未找到配置文件 {}，已跳过通道配置", config_path)
    return True, msg
