# -*- coding: utf-8 -*-
"""
获取本机唯一机器码，用于 License 绑定。
Windows / Mac / Linux 使用各自稳定标识，经哈希后返回统一格式。
"""

import hashlib
import platform
import subprocess
import sys


def _get_windows_machine_id() -> str:
    """Windows: 使用 WMIC CSProduct UUID，失败时用计算机名等组合。"""
    try:
        r = subprocess.run(
            ["wmic", "csproduct", "get", "uuid"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if r.returncode == 0 and r.stdout:
            lines = [x.strip() for x in r.stdout.strip().splitlines() if x.strip()]
            if len(lines) >= 2 and lines[1]:
                return lines[1].strip().upper()
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if r.returncode == 0 and r.stdout and r.stdout.strip():
            return r.stdout.strip().upper()
    except Exception:
        pass
    # 最后回退：主机名 + 系统信息
    return platform.node() + platform.machine() + platform.processor()


def _get_linux_machine_id() -> str:
    """Linux: /etc/machine-id 或 /var/lib/dbus/machine-id。"""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                mid = f.read().strip()
                if mid:
                    return mid
        except OSError:
            continue
    return platform.node() + platform.machine()


def _get_macos_machine_id() -> str:
    """macOS: IOPlatformUUID。"""
    try:
        r = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0 and r.stdout:
            for line in r.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    # 格式通常为 "IOPlatformUUID" = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
                    parts = line.split('"')
                    for i, p in enumerate(parts):
                        if "IOPlatformUUID" in p and i + 2 < len(parts):
                            uuid = parts[i + 2].strip()
                            if uuid and len(uuid) > 10:
                                return uuid
                    break
    except Exception:
        pass
    return platform.node() + platform.machine()


def get_machine_id_raw() -> str:
    """返回当前平台的原始机器标识字符串。"""
    system = platform.system().lower()
    if system == "windows":
        return _get_windows_machine_id()
    if system == "darwin":
        return _get_macos_machine_id()
    return _get_linux_machine_id()


def get_machine_id() -> str:
    """
    返回本机机器码（哈希后的稳定字符串），用于展示与 License 绑定。
    同一台电脑始终返回相同值，不同电脑不同。
    """
    raw = get_machine_id_raw()
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest().upper()[:32]
