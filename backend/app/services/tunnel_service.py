"""内网穿透服务：委托给具体 provider 实现，并管理 JSON 配置文件。

设计决策：
- TunnelService 作为薄封装，持有当前 provider 实例并委托生命周期管理
- 配置存储用 JSON 文件（data/tunnel_config.json），符合 V1.2「可写数据放 data 目录」约束
  - 不建表：内网穿透配置是单行配置，建表过度设计
  - 不入 .env：.env 修改需重启，而隧道配置需热重载
- provider 选择由配置驱动，切换 provider 时先 stop 当前隧道再创建新 provider
- 端口解析：local_port > 0 时用 local_port，否则回退到 settings.APP_PORT

移植自 17_xianyu 的 tunnel_service.py，将 yaml 配置改为 JSON 配置，适配 20_News 架构。
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.paths import resolve_data_dir
from app.services.tunnel_providers import (
    TunnelProvider,
    create_provider,
)

logger = logging.getLogger(__name__)

# 默认配置：首次启动或配置文件丢失时使用
_DEFAULT_CONFIG: dict = {
    "provider": "cloudflare",
    "local_port": 0,           # 0 表示继承 settings.APP_PORT
    "cpolar_authtoken": "",
    "binary_path": "",
    "auto_start": False,
}


def _config_path() -> Path:
    """隧道配置文件路径：data/tunnel_config.json。"""
    return resolve_data_dir() / "tunnel_config.json"


def _load_config() -> dict:
    """读取配置文件，不存在或损坏时回退到默认值。"""
    p = _config_path()
    if not p.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # 合并默认值，避免新增字段缺失
        merged = dict(_DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception as e:
        logger.warning("读取隧道配置失败，使用默认值: %s", e)
        return dict(_DEFAULT_CONFIG)


def _save_config(cfg: dict) -> None:
    """写入配置文件（原子写：先写临时文件再替换）。"""
    p = _config_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


class TunnelService:
    """隧道生命周期管理（委托给 provider）。

    单例：整个应用共享一个隧道实例，通过模块级 get_tunnel_service() 获取。
    """

    def __init__(self):
        self._provider: Optional[TunnelProvider] = None
        self._provider_name: str = ""
        # 配置文件读写无锁，但 save_config 由 API 单线程调用，足够安全
        self._lock = threading.Lock()

    def _resolve_port(self, cfg: dict) -> int:
        """解析实际本地端口：local_port > 0 时用 local_port，否则回退到 APP_PORT。"""
        local_port = cfg.get("local_port", 0)
        if local_port and local_port > 0:
            return int(local_port)
        return get_settings().APP_PORT

    def _ensure_provider(self) -> TunnelProvider:
        """按当前配置创建/复用 provider 实例。"""
        cfg = _load_config()
        provider_name = cfg.get("provider", "cloudflare")

        # 配置未变且 provider 已存在：复用
        if self._provider is not None and self._provider_name == provider_name:
            return self._provider

        # 切换 provider：先停止旧实例
        if self._provider is not None:
            self._provider.stop()
            self._provider = None

        port = self._resolve_port(cfg)
        # 按 provider 类型传递专属参数
        kwargs: dict = {"binary_path": cfg.get("binary_path", "")}
        if provider_name == "cpolar":
            kwargs["authtoken"] = cfg.get("cpolar_authtoken", "")

        self._provider = create_provider(provider_name, port, **kwargs)
        self._provider_name = provider_name
        return self._provider

    @property
    def status(self) -> str:
        """返回隧道状态：running / stopped。"""
        if self._provider is None:
            return "stopped"
        return self._provider.status

    @property
    def public_url(self) -> Optional[str]:
        if self._provider is None:
            return None
        return self._provider.public_url

    @property
    def provider_name(self) -> str:
        """当前 provider 名称（供 API 返回）。

        provider 未创建时回退到配置文件中的 provider 名。
        """
        if self._provider_name:
            return self._provider_name
        return _load_config().get("provider", "cloudflare")

    def start(self) -> str:
        """启动隧道，返回公网 HTTPS URL。"""
        with self._lock:
            provider = self._ensure_provider()
            return provider.start()

    def stop(self) -> None:
        """停止隧道。"""
        with self._lock:
            if self._provider:
                self._provider.stop()

    def get_config(self) -> dict:
        """获取配置（authtoken 脱敏：仅保留末4位）。

        返回字段：
        - provider / local_port / binary_path / auto_start：原值
        - cpolar_authtoken_masked：脱敏后的 token（空值返回空串）
        - cpolar_authtoken_configured：是否已配置 token（布尔）
        """
        cfg = _load_config()
        token = cfg.get("cpolar_authtoken", "")
        # 脱敏：空值返回空串，非空仅显示末4位
        masked_token = token[-4:].rjust(len(token), "•") if token else ""
        return {
            "provider": cfg.get("provider", "cloudflare"),
            "local_port": cfg.get("local_port", 0),
            "cpolar_authtoken_masked": masked_token,
            "cpolar_authtoken_configured": bool(token),
            "binary_path": cfg.get("binary_path", ""),
            "auto_start": cfg.get("auto_start", False),
        }

    def save_config(self, body: dict) -> None:
        """保存配置到 JSON 文件并重置 provider 单例。

        保留已有 authtoken：前端传空串表示「不修改」，只有非空才覆盖。
        配置变更后重置 service 单例，下次 start 时按新配置创建 provider。
        """
        with self._lock:
            existing = _load_config()
            # 前端传空串表示不修改 authtoken
            new_token = body.get("cpolar_authtoken", "") or existing.get("cpolar_authtoken", "")

            new_cfg = {
                "provider": body.get("provider", "cloudflare"),
                "local_port": int(body.get("local_port", 0)),
                "cpolar_authtoken": new_token,
                "binary_path": body.get("binary_path", ""),
                "auto_start": bool(body.get("auto_start", False)),
            }
            _save_config(new_cfg)

            # 配置变更后重置 provider，下次 start 按 new_cfg 创建
            if self._provider is not None:
                self._provider.stop()
                self._provider = None
                self._provider_name = ""


# 模块级单例：整个应用共享一个隧道实例
_tunnel_service: Optional[TunnelService] = None


def get_tunnel_service() -> TunnelService:
    """获取或创建全局 TunnelService 单例。"""
    global _tunnel_service
    if _tunnel_service is None:
        _tunnel_service = TunnelService()
    return _tunnel_service


def reset_tunnel_service() -> None:
    """重置单例（测试用）。"""
    global _tunnel_service
    if _tunnel_service is not None:
        _tunnel_service.stop()
    _tunnel_service = None
