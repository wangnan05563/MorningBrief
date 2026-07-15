"""密钥加密存储（对标 17_xianyu secrets.py）。

安全层级：
1. keyring（首选）：Windows DPAPI / macOS Keychain / Linux Secret Service
   绑定当前用户账号，跨用户/跨机器不可读
2. fallback：base64 编码 + 文件权限限制
   弱保护，仅防"肉眼误看"；不防"有意读取"，启动时打印一次性警告

为什么不用 Fernet 等真加密：密钥本身需要另一个密钥来加密，
对本地单用户工具来说，密钥管理复杂度远超安全收益。
keyring 才是正确方案，fallback 只是兜底。

使用方式：
    from app.core.secrets import get_secret, set_secret
    set_secret("llm_api_key", "sk-xxx")
    key = get_secret("llm_api_key")  # "sk-xxx"

迁移助手：从 .env 读取敏感 Key 迁移到 keyring，成功后替换为占位符。
    migrate_from_env()  # 一次性迁移
"""
from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path

# keyring 在 Windows 上使用 Windows Credential Locker，
# 在底层调用 DPAPI 进行加密，绑定当前 Windows 用户账号。
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

from loguru import logger

# 服务名（keyring 中的"应用名"分组）
SERVICE_NAME = "MorningBrief"

# MorningBrief 已知的敏感配置键（与 Settings 字段对应）
# 启动时 config.py 可优先从 keyring 读取这些键
SENSITIVE_KEYS = {
    "llm_api_key": "LLM_API_KEY",
    "tts_api_key": "ALIYUN_TTS_API_KEY",
    "cos_secret_id": "COS_SECRET_ID",
    "cos_secret_key": "COS_SECRET_KEY",
    "wx_secret": "WX_SECRET",
    "alert_sms_access_key": "ALERT_SMS_ACCESS_KEY",
    "alert_sms_secret_key": "ALERT_SMS_SECRET_KEY",
}


def is_available() -> bool:
    """检查 keyring 在当前系统是否可用。"""
    return KEYRING_AVAILABLE


def set_secret(key: str, value: str) -> None:
    """存储一个密钥到 keyring。

    keyring 不可用时回退到 base64 编码文件（弱保护）。
    """
    if not KEYRING_AVAILABLE:
        logger.warning("keyring 不可用，回退到 base64 文件存储")
        _fallback_set(key, value)
        return
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        logger.debug("已加密存储 %s", key)
    except Exception:
        logger.exception("keyring 存储失败 %s，回退到 base64 文件", key)
        _fallback_set(key, value)


def get_secret(key: str) -> str | None:
    """读取密钥。

    keyring 不可用时从 base64 文件读取。
    """
    if not KEYRING_AVAILABLE:
        return _fallback_get(key)
    try:
        return keyring.get_password(SERVICE_NAME, key)
    except Exception:
        logger.exception("keyring 读取失败 %s", key)
        return _fallback_get(key)


def delete_secret(key: str) -> None:
    """删除一个密钥。"""
    if KEYRING_AVAILABLE:
        try:
            keyring.delete_password(SERVICE_NAME, key)
            return
        except Exception:
            pass
    _fallback_delete(key)


def list_keys() -> list[str]:
    """列出所有已存密钥（仅名字）。

    keyring 没有 list 接口，遍历预定义键判断是否存在。
    """
    if KEYRING_AVAILABLE:
        try:
            return [k for k in SENSITIVE_KEYS if get_secret(k) is not None]
        except Exception:
            return []
    return list(_fallback_all().keys())


def migrate_from_env(env_path: str = ".env") -> int:
    """从 .env 文件读取敏感 Key 并迁移到 keyring，成功后替换为占位符。

    返回迁移的 Key 数量。迁移后 .env 中对应行替换为
    `KEY=__MIGRATED_TO_KEYRING__`，config.py 加载时识别此占位符并从 keyring 读取。

    使用场景：首次启用 keyring 后一次性迁移，避免敏感信息明文留在 .env。
    """
    env_file = Path(env_path)
    if not env_file.exists():
        return 0

    count = 0
    new_lines = []
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not _is_env_entry(line):
            new_lines.append(line)
            continue
        key, value = _parse_env_line(line)
        migrated, new_line, did_migrate = _try_migrate_key(key, value)
        if did_migrate:
            count += 1
        new_lines.append(new_line if migrated else line)

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return count


def _is_env_entry(line: str) -> bool:
    """判断是否为有效的 .env 键值行（非空、非注释、包含 =）。"""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#") and "=" in stripped


def _parse_env_line(line: str) -> tuple[str, str]:
    """解析 .env 行为 (key, value)，均已 strip。"""
    key, _, value = line.partition("=")
    return key.strip(), value.strip()


def _try_migrate_key(key: str, value: str) -> tuple[bool, str, bool]:
    """尝试迁移单个环境变量键到 keyring。

    返回 (是否已处理, 新行内容, 是否实际执行了迁移)。
    - 已是占位符 → (True, 原行, False)
    - 成功迁移 → (True, 占位符行, True)
    - 未匹配 → (False, 原行, False)
    """
    env_key_lower = key.lower()
    for secret_key, settings_attr in SENSITIVE_KEYS.items():
        if env_key_lower != settings_attr.lower() or not value:
            continue
        # 跳过已是占位符的行
        if value == "__MIGRATED_TO_KEYRING__":
            return True, f"{key}=__MIGRATED_TO_KEYRING__", False
        set_secret(secret_key, value)
        logger.info("已迁移 %s → keyring", key)
        return True, f"{key}=__MIGRATED_TO_KEYRING__", True
    return False, "", False


# ============== 回退实现（keyring 不可用时） ==============

_FALLBACK_FILE = Path("data/.secrets.json")
_FALLBACK_WARNED = False


def _warn_fallback() -> None:
    """首次使用 fallback 时打印一次性警告。"""
    global _FALLBACK_WARNED
    if not _FALLBACK_WARNED:
        _FALLBACK_WARNED = True
        logger.warning(
            "keyring 不可用，密钥以 base64 编码存储在 "
            f"{_FALLBACK_FILE}（弱保护）。建议安装 keyring 后运行 "
            "migrate_from_env() 迁移到系统密钥库。"
        )


def _obfuscate(value: str) -> str:
    """base64 编码：不是加密，仅防止肉眼直接看到明文。"""
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _deobfuscate(value: str) -> str:
    """base64 解码。"""
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


def _set_file_permissions(path: Path) -> None:
    """限制文件权限为仅当前用户可读写（Unix: 600, Windows: best-effort）。"""
    try:
        if os.name != "nt":
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _fallback_set(key: str, value: str) -> None:
    _warn_fallback()
    _FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = _fallback_all()
    data[key] = _obfuscate(value)
    _FALLBACK_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _set_file_permissions(_FALLBACK_FILE)


def _fallback_get(key: str) -> str | None:
    raw = _fallback_all().get(key)
    if raw is None:
        return None
    try:
        return _deobfuscate(raw)
    except Exception:
        # 兼容旧版明文存储的值
        return raw


def _fallback_delete(key: str) -> None:
    data = _fallback_all()
    if key in data:
        del data[key]
        _FALLBACK_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _fallback_all() -> dict[str, str]:
    if not _FALLBACK_FILE.exists():
        return {}
    try:
        return json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
