# -*- coding: utf-8 -*-
"""
未检测到 Docker 时，自动下载并启动安装程序。
支持 Windows（Docker Desktop）、macOS（Docker.dmg）、Linux（get.docker.com 脚本）。
"""

import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
from typing import Tuple

from loguru import logger


# 官方安装包下载地址（Docker Desktop）
DOCKER_WIN_AMD64 = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
DOCKER_WIN_ARM64 = "https://desktop.docker.com/win/main/arm64/Docker%20Desktop%20Installer.exe"
DOCKER_MAC_AMD64 = "https://desktop.docker.com/mac/main/amd64/Docker.dmg"
DOCKER_MAC_ARM64 = "https://desktop.docker.com/mac/main/arm64/Docker.dmg"
DOCKER_LINUX_SCRIPT = "https://get.docker.com"


def _get_download_url() -> Tuple[str, str]:
    """
    根据当前系统返回 (下载 URL, 本地保存文件名)。
    若当前平台不支持自动安装，返回 ("", "")。
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        if machine in ("arm64", "aarch64"):
            return DOCKER_WIN_ARM64, "Docker Desktop Installer.exe"
        return DOCKER_WIN_AMD64, "Docker Desktop Installer.exe"
    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return DOCKER_MAC_ARM64, "Docker.dmg"
        return DOCKER_MAC_AMD64, "Docker.dmg"
    if system == "linux":
        return DOCKER_LINUX_SCRIPT, "get-docker.sh"
    return "", ""


def _download_file(url: str, dest_path: str) -> Tuple[bool, str]:
    """下载文件到指定路径。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-Deploy/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(dest_path, "wb") as f:
                f.write(resp.read())
        return True, ""
    except Exception as e:
        return False, str(e)


def _run_installer_windows(installer_path: str) -> Tuple[bool, str]:
    """Windows：启动 Docker Desktop 安装程序（可能需管理员权限）。"""
    try:
        # 先尝试静默安装；若需用户确认则直接运行安装程序
        subprocess.Popen(
            [installer_path, "install", "--quiet"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return True, "Docker 安装程序已启动，请按提示完成安装（如需管理员权限请选择“是”）。安装完成后请重新运行本工具。"
    except Exception as e1:
        try:
            # 无静默参数，仅启动安装向导
            subprocess.Popen(
                [installer_path],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return True, "Docker 安装程序已启动，请按提示完成安装。安装完成后请重新运行本工具。"
        except Exception as e2:
            return False, f"无法启动安装程序: {e2}"


def _run_installer_mac(dmg_path: str) -> Tuple[bool, str]:
    """macOS：挂载 DMG 并打开，由用户拖拽到应用程序。"""
    try:
        subprocess.Popen(["open", dmg_path])
        return True, "Docker 安装镜像已打开，请将 Docker 拖入“应用程序”文件夹，然后从应用程序启动 Docker。完成后请重新运行本工具。"
    except Exception as e:
        return False, f"无法打开安装镜像: {e}"


def _run_installer_linux(script_path: str) -> Tuple[bool, str]:
    """Linux：尝试用 sudo 执行 get-docker.sh；若无法 sudo 则提示用户手动执行。"""
    try:
        r = subprocess.run(
            ["sudo", "sh", script_path],
            timeout=300,
        )
        if r.returncode == 0:
            return True, "Docker 已安装，请重新运行本工具进行部署。"
        return True, f"安装脚本已保存到 {script_path} ，请在终端执行以下命令完成安装（需输入密码）:\n  sudo sh {script_path}\n安装完成后请重新运行本工具。"
    except FileNotFoundError:
        return True, f"安装脚本已保存到 {script_path} ，请在终端执行: sudo sh {script_path}\n安装完成后请重新运行本工具。"
    except subprocess.TimeoutExpired:
        return False, "安装脚本执行超时"
    except Exception as e:
        return True, f"安装脚本已保存到 {script_path} ，请在终端执行: sudo sh {script_path}\n（若需密码请在本机终端输入）\n错误: {e}"


def download_and_launch_docker_installer() -> Tuple[bool, str]:
    """
    检测当前系统，自动下载 Docker 安装包并启动安装程序。
    返回 (是否已启动安装, 提示信息)。
    """
    url, filename = _get_download_url()
    if not url:
        return False, f"当前系统（{platform.system()}）暂不支持自动安装 Docker，请手动访问 https://docs.docker.com/get-docker/ 安装。"

    logger.info("正在下载 Docker 安装程序: {}", url)
    save_dir = tempfile.gettempdir()
    if platform.system().lower() == "linux" and url == DOCKER_LINUX_SCRIPT:
        save_path = os.path.join(save_dir, filename)
    else:
        save_path = os.path.join(save_dir, filename)

    ok, err = _download_file(url, save_path)
    if not ok:
        logger.error("下载失败: {}", err)
        return False, f"Docker 安装程序下载失败: {err}。请手动从 https://docs.docker.com/get-docker/ 下载安装。"

    logger.info("下载完成: {}", save_path)
    system = platform.system().lower()

    if system == "windows":
        return _run_installer_windows(save_path)
    if system == "darwin":
        return _run_installer_mac(save_path)
    if system == "linux":
        return _run_installer_linux(save_path)
    return False, "不支持的操作系统"