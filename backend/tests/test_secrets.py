"""密钥管理模块测试。

覆盖：
- keyring 不可用时回退到 base64 文件存储
- set/get/delete 往返一致性
- migrate_from_env 迁移 .env 敏感键到 keyring
- 占位符跳过迁移
- list_keys 列举已存密钥

为避免污染真实 keyring（Windows Credential Locker），
测试强制 KEYRING_AVAILABLE=False 走 fallback 路径。
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core import secrets as secrets_mod


@pytest.fixture(autouse=True)
def _isolated_fallback(tmp_path, monkeypatch):
    """每个测试用临时 fallback 文件，避免污染 data/.secrets.json。"""
    fake_file = tmp_path / ".secrets.json"
    monkeypatch.setattr(secrets_mod, "_FALLBACK_FILE", fake_file)
    # 重置一次性警告标志，保证下次测试可重新触发警告
    monkeypatch.setattr(secrets_mod, "_FALLBACK_WARNED", False)
    # 强制 keyring 不可用，走 fallback
    monkeypatch.setattr(secrets_mod, "KEYRING_AVAILABLE", False)
    yield


def test_set_and_get_secret():
    """fallback 模式下 set/get 往返一致。"""
    secrets_mod.set_secret("llm_api_key", "sk-test-123")
    assert secrets_mod.get_secret("llm_api_key") == "sk-test-123"


def test_get_nonexistent_returns_none():
    """读取不存在的 key 返回 None。"""
    assert secrets_mod.get_secret("not_exists") is None


def test_delete_secret():
    """删除后读取返回 None。"""
    secrets_mod.set_secret("tts_api_key", "key-abc")
    secrets_mod.delete_secret("tts_api_key")
    assert secrets_mod.get_secret("tts_api_key") is None


def test_delete_nonexistent_no_error():
    """删除不存在的 key 不抛异常。"""
    secrets_mod.delete_secret("never_existed")


def test_fallback_file_is_base64_not_plaintext():
    """fallback 文件内容应是 base64 编码，非明文。"""
    secrets_mod.set_secret("llm_api_key", "sk-secret-value")
    raw = secrets_mod._FALLBACK_FILE.read_text(encoding="utf-8")
    data = json.loads(raw)
    # 明文不应直接出现在文件中
    assert "sk-secret-value" not in raw
    assert data["llm_api_key"] != "sk-secret-value"


def test_list_keys_fallback():
    """fallback 模式下 list_keys 返回已存密钥名。"""
    secrets_mod.set_secret("llm_api_key", "v1")
    secrets_mod.set_secret("tts_api_key", "v2")
    keys = secrets_mod.list_keys()
    assert "llm_api_key" in keys
    assert "tts_api_key" in keys


def test_migrate_from_env(tmp_path):
    """migrate_from_env 迁移敏感键并替换为占位符。"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_API_KEY=sk-migrate-me\n"
        "COS_SECRET_ID=ak-123\n"
        "NON_SENSITIVE=keep-me\n",
        encoding="utf-8",
    )
    count = secrets_mod.migrate_from_env(str(env_file))
    assert count == 2

    # 验证 keyring 已存储
    assert secrets_mod.get_secret("llm_api_key") == "sk-migrate-me"
    assert secrets_mod.get_secret("cos_secret_id") == "ak-123"

    # 验证 .env 替换为占位符
    content = env_file.read_text(encoding="utf-8")
    assert "LLM_API_KEY=__MIGRATED_TO_KEYRING__" in content
    assert "COS_SECRET_ID=__MIGRATED_TO_KEYRING__" in content
    assert "NON_SENSITIVE=keep-me" in content


def test_migrate_skips_already_migrated(tmp_path):
    """已是占位符的行不再迁移。"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_API_KEY=__MIGRATED_TO_KEYRING__\n",
        encoding="utf-8",
    )
    count = secrets_mod.migrate_from_env(str(env_file))
    assert count == 0


def test_migrate_nonexistent_file():
    """.env 不存在时返回 0。"""
    assert secrets_mod.migrate_from_env("/nonexistent/.env") == 0


def test_migrate_preserves_comments_and_empty_lines(tmp_path):
    """注释和空行原样保留。"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Comment line\n"
        "\n"
        "LLM_API_KEY=sk-value\n",
        encoding="utf-8",
    )
    secrets_mod.migrate_from_env(str(env_file))
    content = env_file.read_text(encoding="utf-8")
    assert "# Comment line" in content
    # 空行保留
    assert "\n\n" in content or content.startswith("\n")
