# -*- coding: utf-8 -*-
"""工具端 loguru 日志配置：写入用户目录日志文件并输出到控制台。"""

import os
import sys

from loguru import logger


def init_tool_logger(level: str = "INFO") -> None:
    """初始化工具端日志：控制台 + 用户目录下的日志文件。"""
    logger.remove()
    # 控制台（部分 loguru 版本不支持 encoding 参数，此处省略）
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=level,
    )
    # 用户目录日志文件（打包后与源码运行均可用）
    log_dir = os.path.join(os.path.expanduser("~"), ".openclaw_deploy", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "tool.log")
    logger.add(
        log_file,
        rotation="5 MB",
        retention="7 days",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )
