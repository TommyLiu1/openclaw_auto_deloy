# -*- coding: utf-8 -*-
"""
命令行入口：校验 License（本机绑定）后执行一键部署。
通道配置文件默认放在与可执行文件同一目录，启动时自动读取。
"""

import argparse
import os
import sys

from loguru import logger

# 与可执行文件同目录时的默认通道配置文件名
CHANNELS_CONFIG_FILENAME = "channels.json"


def get_default_config_path() -> str:
    """
    返回默认通道配置文件的路径。
    打包为 exe 时：与可执行文件同一目录下的 channels.json；
    否则：当前工作目录下的 channels.json。
    """
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.getcwd()
    return os.path.join(base_dir, CHANNELS_CONFIG_FILENAME)

from . import __version__
from . import license as license_mod
from . import machine_id
from . import deploy
from .logger import init_tool_logger


def _ensure_utf8():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _check_license(license_key: str) -> bool:
    """向服务器提交 License Key 与本机 machine_id，激活或验证通过后返回 True。"""
    mid = machine_id.get_machine_id()
    logger.info("正在向服务器验证 License（本机 machine_id 已上传）")
    ok, err = license_mod.activate_and_verify(license_key, mid)
    if not ok:
        logger.error("License 校验失败: {}", err)
        return False
    logger.info("License 验证通过，已绑定本机")
    return True


def cmd_machine_id(_: argparse.Namespace) -> int:
    """输出本机机器码（激活时会上传至服务器并绑定 License）。"""
    _ensure_utf8()
    mid = machine_id.get_machine_id()
    logger.info("本机机器码: {}", mid)
    print("本机机器码（输入 License Key 后将与此机器绑定）：")
    print(mid)
    return 0


def _prompt_license_key() -> str:
    """在控制台交互式提示用户输入 License Key（双击运行时使用）。"""
    try:
        print("请输入 License Key（验证通过后将绑定本机并自动保存）：", flush=True)
        line = input("License Key: ").strip()
        return line or ""
    except EOFError:
        return ""
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return ""


def cmd_deploy(args: argparse.Namespace) -> int:
    """校验 License 后执行一键部署。"""
    _ensure_utf8()
    license_key = args.license or license_mod.load_license_from_file()
    if not license_key:
        # 双击运行时提供命令行交互，让用户输入 License Key
        license_key = _prompt_license_key()
    if not license_key:
        logger.warning("未提供 License Key")
        print("未输入 License Key，已退出。", file=sys.stderr)
        print("  方式一: 双击运行后按提示输入 License Key", file=sys.stderr)
        print("  方式二: 使用 --license YOUR_KEY", file=sys.stderr)
        print("  方式三: 首次验证通过后会自动保存，之后无需重复输入。", file=sys.stderr)
        return 1
    if not _check_license(license_key):
        return 1
    if not args.license and license_mod.load_license_from_file() != license_key:
        license_mod.save_license_to_file(license_key)
        logger.info("已保存 License 到本地")
    logger.info("开始执行一键部署")
    # 仅当显式传入 --config 时使用通道配置；不默认查找 channels.json
    config_path = getattr(args, "config", None)
    if config_path and os.path.isfile(config_path):
        logger.info("使用通道配置: {}", config_path)
    ok, msg = deploy.run_deploy(config_path=config_path)
    if ok:
        logger.info("部署成功: {}", msg)
        print(msg)
        return 0
    logger.error("部署失败: {}", msg)
    print(msg, file=sys.stderr)
    return 1


def cmd_verify(args: argparse.Namespace) -> int:
    """仅校验 License，不部署。"""
    _ensure_utf8()
    license_key = args.license or license_mod.load_license_from_file()
    if not license_key:
        logger.warning("未提供 License Key")
        print("请使用 --license YOUR_KEY 指定要校验的 License。", file=sys.stderr)
        return 1
    if _check_license(license_key):
        print("License 验证通过，已绑定本机，可执行一键部署。")
        return 0
    return 1


def main() -> int:
    init_tool_logger()
    parser = argparse.ArgumentParser(
        description="OpenClaw 一键部署工具（支持 Windows / Mac / Linux，License 本机绑定）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  openclaw-deploy --machine-id
  openclaw-deploy --license YOUR_LICENSE_KEY
  openclaw-deploy --config channels.json
  openclaw-deploy
        """,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--machine-id", action="store_true", help="输出本机机器码，用于申请 License")
    parser.add_argument("--license", "-l", metavar="KEY", help="License Key（与本机绑定）")
    parser.add_argument("--verify", action="store_true", help="仅校验 License，不执行部署")
    parser.add_argument(
        "--config", "-c",
        metavar="PATH",
        help="通道配置文件路径（JSON）。未指定时不加载通道配置，仅按 OpenClaw-Docker-CN-IM 方式启动容器",
    )

    args = parser.parse_args()
    logger.debug("命令行参数: {}", args)

    if args.machine_id:
        return cmd_machine_id(args)
    if args.verify:
        return cmd_verify(args)
    return cmd_deploy(args)


if __name__ == "__main__":
    sys.exit(main())
