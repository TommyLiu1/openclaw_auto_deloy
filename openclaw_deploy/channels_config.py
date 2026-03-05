# -*- coding: utf-8 -*-
"""
从用户提供的配置文件解析 QQ、钉钉、企业微信、飞书等通道配置，
并合并到 OpenClaw 的 openclaw.json；配置完成后校验是否生效。
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# 支持的通道在 openclaw.json 中的 key（与官方文档一致）
SUPPORTED_CHANNELS = ("feishu", "wecom", "dingtalk", "qq", "qqbot")

# 各通道至少需包含的字段（用于校验配置是否完整）
CHANNEL_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "feishu": ["accounts"],  # 至少要有 accounts.main.appId + appSecret
    "wecom": [],  # corpId, agentId, secret 等，结构多样
    "dingtalk": [],
    "qq": [],
    "qqbot": [],
}


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_user_config(path: str) -> Dict[str, Any]:
    """加载用户配置文件，支持 .json。返回内容需包含 channels 或顶层即通道名。"""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")
    raw = _load_json(path)
    if "channels" in raw:
        return raw["channels"]
    # 顶层即为通道名
    return {k: v for k, v in raw.items() if k in SUPPORTED_CHANNELS and isinstance(v, dict)}


def load_and_normalize_user_channels(path: str) -> Dict[str, Any]:
    """
    加载用户配置并规范为可合并的 channels 字典。
    只保留支持的通道名及非空配置；若某通道 enabled=False 或缺少必要信息则仍保留由 OpenClaw 默认处理。
    """
    channels = _load_user_config(path)
    out: Dict[str, Any] = {}
    for name, cfg in channels.items():
        if name not in SUPPORTED_CHANNELS:
            logger.debug("跳过不支持的通道: {}", name)
            continue
        if not isinstance(cfg, dict):
            continue
        # 统一设为 enabled 以便生效（用户未写则默认 True）
        merged = dict(cfg)
        if "enabled" not in merged:
            merged["enabled"] = True
        out[name] = merged
        logger.info("已解析用户配置: 通道 {} 已启用", name)
    return out


def merge_channels_into_openclaw(openclaw_data: Dict[str, Any], user_channels: Dict[str, Any]) -> Dict[str, Any]:
    """将用户通道配置合并进 openclaw 完整配置，不覆盖未在用户配置中出现的通道。"""
    out = dict(openclaw_data)
    if "channels" not in out:
        out["channels"] = {}
    for name, cfg in user_channels.items():
        out["channels"][name] = {**(out["channels"].get(name) or {}), **cfg}
    return out


def has_channel_credentials(channel_name: str, cfg: Dict[str, Any]) -> bool:
    """简单判断该通道配置是否包含凭证信息（是否算“已配置”）。"""
    if not cfg or cfg.get("enabled") is False:
        return False
    if channel_name == "feishu":
        acc = cfg.get("accounts") or {}
        if isinstance(acc, dict):
            for v in acc.values():
                if isinstance(v, dict) and (v.get("appId") or v.get("appSecret")):
                    return True
        return False
    if channel_name in ("wecom", "wechat_work"):
        return bool(cfg.get("corpId") or cfg.get("secret") or (cfg.get("accounts") and isinstance(cfg["accounts"], dict)))
    if channel_name == "dingtalk":
        return bool(cfg.get("appKey") or cfg.get("appSecret"))
    if channel_name in ("qq", "qqbot"):
        return bool(cfg.get("appId") or cfg.get("token"))
    return bool(cfg)


def verify_channels_in_openclaw(openclaw_data: Dict[str, Any], expected_channels: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    校验 openclaw 配置中是否已包含用户配置的通道且具备凭证。
    返回 (全部通过, 错误/提示信息列表)。
    """
    channels = openclaw_data.get("channels") or {}
    errors: List[str] = []
    for name, user_cfg in expected_channels.items():
        if user_cfg.get("enabled") is False:
            continue
        current = channels.get(name)
        if not current:
            errors.append(f"通道 {name} 未在 openclaw.json 的 channels 中找到")
            continue
        if not has_channel_credentials(name, current):
            errors.append(f"通道 {name} 已存在但缺少必要凭证（如 appId/appSecret、token 等）")
    return len(errors) == 0, errors
