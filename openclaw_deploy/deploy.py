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
from . import docker_installer as docker_inst


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


def _get_compose_dir() -> str:
    """获取 docker-compose.yml 与 .env 所在目录：打包为 exe 时为 exe 同目录，否则为 openclaw_deploy 包目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# 单容器回退时使用的默认镜像（docker hub 上 openclaw/openclaw 不存在，改用可用镜像）
# 若同目录存在 .env 且含 OPENCLAW_IMAGE，则优先使用该值
DEFAULT_OPENCLAW_IMAGE = "justlikemaki/openclaw-docker-cn-im:latest"

# Docker 镜像加速源（用于 daemon.json registry-mirrors，可任选一个或多个）
DEFAULT_REGISTRY_MIRRORS = [
    "https://docker.m.daocloud.io",
    "https://noohub.ru",
    "https://huecker.io",
    "https://dockerhub.timeweb.cloud",
    "http://mirrors.ustc.edu.cn/",
    "http://mirror.azure.cn/",
    "https://hub.rat.dev/",
    "https://docker.ckyl.me/",
]


def _get_docker_daemon_json_path() -> str:
    """返回当前平台 Docker daemon.json 的路径（Windows/Linux/macOS）。"""
    if sys.platform == "win32":
        # 优先用 USERPROFILE，双击运行 exe 时更可靠
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        return os.path.join(home, ".docker", "daemon.json")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), ".docker", "daemon.json")
    return "/etc/docker/daemon.json"


def _ensure_docker_registry_mirrors() -> Tuple[bool, str]:
    """
    确保 Docker daemon 已配置国内镜像加速（registry-mirrors）。
    若已存在非空 registry-mirrors 则不改动；否则尝试写入默认国内源。
    返回 (是否已写入或已存在有效配置, 提示信息)。
    """
    path = _get_docker_daemon_json_path()
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            mirrors = data.get("registry-mirrors")
            if isinstance(mirrors, list) and len(mirrors) > 0:
                return True, "Docker 已配置镜像加速，将从国内源拉取镜像"
            # 有文件但无有效 mirrors，合并
            data["registry-mirrors"] = DEFAULT_REGISTRY_MIRRORS
        else:
            data = {"registry-mirrors": DEFAULT_REGISTRY_MIRRORS}
            dirpath = os.path.dirname(path)
            if dirpath and not os.path.isdir(dirpath):
                os.makedirs(dirpath, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        reload_hint = (
            "Linux 下请执行：systemctl daemon-reload && systemctl restart docker"
            if sys.platform != "win32" and sys.platform != "darwin"
            else "请重启 Docker Desktop 使配置生效"
        )
        return True, (
            "已写入镜像加速配置至 {}。{}。".format(path, reload_hint)
        )
    except (OSError, PermissionError) as e:
        reload_cmd = (
            "保存后执行：systemctl daemon-reload && systemctl restart docker"
            if sys.platform != "win32" and sys.platform != "darwin"
            else "保存后重启 Docker"
        )
        hint = (
            "无法写入 Docker 配置 {}，将直接拉取镜像（可能较慢）。"
            "可手动在该文件中添加 \"registry-mirrors\": {}，{}。"
        ).format(path, json.dumps(DEFAULT_REGISTRY_MIRRORS, ensure_ascii=False), reload_cmd)
        logger.warning("{} 错误: {}", hint, e)
        return False, hint
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("解析 {} 失败: {}，将直接拉取镜像", path, e)
        return False, "Docker 配置文件格式异常，将直接拉取镜像（可能较慢）。"


def _get_fallback_openclaw_image() -> str:
    """单容器回退时使用的镜像：优先从 .env 的 OPENCLAW_IMAGE 读取。"""
    env_file = os.path.join(_get_compose_dir(), ".env")
    if os.path.isfile(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENCLAW_IMAGE=") and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass
    return DEFAULT_OPENCLAW_IMAGE


def deploy_with_docker() -> Tuple[bool, str, str, str]:
    """
    使用 Docker 部署 OpenClaw：优先使用 openclaw_deploy 下的 docker-compose.yml 与 .env，否则回退到单容器 run。
    返回 (成功, 消息, 容器名, 容器内 openclaw.json 路径)。
    """
    _ensure_utf8()
    # 无论 compose 还是单容器，都先尝试写入镜像加速配置，便于后续 pull 走国内源
    _, mirror_hint = _ensure_docker_registry_mirrors()
    logger.info("{}", mirror_hint)
    compose_dir = _get_compose_dir()
    compose_file = os.path.join(compose_dir, "docker-compose.yml")
    env_file = os.path.join(compose_dir, ".env")

    if os.path.isfile(compose_file):
        logger.info("使用 docker-compose 部署，compose 文件: {}", compose_file)
        cmd = ["docker", "compose", "-f", compose_file]
        if os.path.isfile(env_file):
            cmd += ["--env-file", env_file]
            logger.info("使用环境变量文件: {}", env_file)
        cmd += ["up", "-d"]
        ok, out = _run(cmd, timeout=120, shell=False)
        if not ok:
            logger.error("docker compose 启动失败: {}", out)
            return False, f"docker compose 启动失败: {out}", "openclaw-gateway", "/home/node/.openclaw/openclaw.json"
        logger.info("Docker Compose 已启动")
        gateway_port = "18789"
        if os.path.isfile(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENCLAW_GATEWAY_PORT=") and "=" in line:
                            gateway_port = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
        return True, f"Docker Compose 部署成功。管理界面: http://127.0.0.1:{gateway_port}/", "openclaw-gateway", "/home/node/.openclaw/openclaw.json"

    logger.info("检测到 Docker，使用单容器方式部署（参考 OpenClaw-Docker-CN-IM）")
    image = _get_fallback_openclaw_image()
    logger.info("使用镜像: {}（首次拉取可能需数分钟，请耐心等待）", image)
    # 镜像体积较大或网络较慢时拉取可能较久，超时设为 20 分钟
    ok, out = _run(["docker", "pull", image], timeout=1200)
    if not ok:
        logger.error("拉取镜像失败: {}", out)
        return False, f"拉取镜像失败: {out}", "openclaw-gateway", "/home/node/.openclaw/openclaw.json"
    _run(["docker", "stop", "openclaw-gateway"], timeout=30)
    _run(["docker", "rm", "openclaw-gateway"], timeout=10)
    # 与 https://github.com/justlovemaki/OpenClaw-Docker-CN-IM 一致：容器名、挂载路径、端口、cap；从 .env 注入环境变量供 init 生成 openclaw.json
    cmd = [
        "docker", "run", "-d",
        "--name", "openclaw-gateway",
        "--restart", "unless-stopped",
        "-p", "127.0.0.1:18789:18789",
        "-p", "127.0.0.1:18790:18790",
        "-v", "openclaw-data:/home/node/.openclaw",
        "--cap-add", "CHOWN",
        "--cap-add", "SETUID",
        "--cap-add", "SETGID",
        "--cap-add", "DAC_OVERRIDE",
    ]
    if os.path.isfile(env_file):
        cmd += ["--env-file", env_file]
        logger.info("单容器使用环境变量文件: {}（用于生成 openclaw.json）", env_file)
    cmd.append(image)
    ok, out = _run(cmd, timeout=60)
    if not ok:
        logger.error("启动容器失败: {}", out)
        return False, f"启动容器失败: {out}", "openclaw-gateway", "/home/node/.openclaw/openclaw.json"
    logger.info("Docker 容器已启动")
    return True, "Docker 部署成功。管理界面: http://127.0.0.1:18789/ ，如需配对可执行: docker exec -it openclaw-gateway openclaw pairing approve <channel> <token>", "openclaw-gateway", "/home/node/.openclaw/openclaw.json"


def _apply_channels_config_docker(
    user_config_path: str,
    container_name: str = "openclaw-gateway",
    config_path_in_container: str = "/home/node/.openclaw/openclaw.json",
) -> Tuple[bool, str]:
    """在 Docker 容器内应用用户通道配置并重启网关。"""
    try:
        user_channels = ch_cfg.load_and_normalize_user_channels(user_config_path)
    except FileNotFoundError as e:
        return False, str(e)
    except json.JSONDecodeError as e:
        return False, f"配置文件不是合法 JSON: {e}"
    if not user_channels:
        return True, "配置文件中无支持的通道（feishu/wecom/dingtalk/qq），已跳过"
    ok, out = _run(["docker", "exec", container_name, "cat", config_path_in_container], timeout=10)
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
        ok, out = _run(["docker", "cp", tmp, f"{container_name}:{config_path_in_container}"], timeout=10)
        if not ok:
            return False, f"写入容器配置失败: {out}"
        ok, out = _run(["docker", "exec", container_name, "openclaw", "gateway", "restart"], timeout=30)
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


def _verify_channels_config_docker(
    user_config_path: str,
    container_name: str = "openclaw-gateway",
    config_path_in_container: str = "/home/node/.openclaw/openclaw.json",
) -> Tuple[bool, str]:
    """校验 Docker 容器内通道配置是否生效。"""
    try:
        user_channels = ch_cfg.load_and_normalize_user_channels(user_config_path)
    except Exception:
        return True, "未使用通道配置或解析失败，跳过校验"
    if not user_channels:
        return True, "无通道需校验"
    ok, out = _run(["docker", "exec", container_name, "cat", config_path_in_container], timeout=10)
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
    docker_container_name: str = "openclaw",
    docker_config_path: str = "/root/.openclaw/openclaw.json",
) -> Tuple[bool, str]:
    """应用用户通道配置并校验是否成功。Docker 时需传入容器名与容器内配置路径。"""
    if use_docker:
        ok, msg = _apply_channels_config_docker(user_config_path, docker_container_name, docker_config_path)
    else:
        ok, msg = _apply_channels_config_node(user_config_path)
    if not ok:
        return False, msg
    logger.info("应用配置: {}", msg)
    if use_docker:
        ok, msg = _verify_channels_config_docker(user_config_path, docker_container_name, docker_config_path)
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
    container_name = "openclaw-gateway"
    config_path_in_container = "/home/node/.openclaw/openclaw.json"
    if use_docker:
        logger.debug("已检测到 Docker")
        ok, msg, container_name, config_path_in_container = deploy_with_docker()
    elif has_node22() and platform.system().lower() != "windows":
        # Node 方式仅用于 Linux/Mac；Windows 必须使用 Docker
        logger.debug("已检测到 Node.js 22+，使用 Node 方式部署")
        ok, msg = deploy_with_node()
    else:
        # Windows 未装 Docker 或 本机既无 Docker 也无 Node22：先尝试自动下载并启动 Docker 安装程序
        logger.warning("未检测到 Docker，尝试自动下载并启动安装程序")
        install_ok, install_msg = docker_inst.download_and_launch_docker_installer()
        if install_ok:
            return False, install_msg + "\n\n完成安装后请重新运行本工具进行一键部署。"
        return False, (
            install_msg + "\n\n或手动安装：\n"
            "  - Docker: https://docs.docker.com/get-docker/\n"
            "  - Node.js 22+: https://nodejs.org/"
        )
    if not ok:
        return False, msg
    if config_path and os.path.isfile(config_path):
        ok2, msg2 = apply_and_verify_channels_config(
            config_path, use_docker, container_name, config_path_in_container
        )
        if not ok2:
            return False, msg2
        msg = msg + "\n通道配置已应用并校验通过。"
    elif config_path:
        logger.warning("未找到配置文件 {}，已跳过通道配置", config_path)
    return True, msg
