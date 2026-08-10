"""COS 配置服务单元测试。

覆盖：
1. 脱敏格式（_mask_key）
2. 配置读取（默认值 / 脱敏返显 / configured 口径）
3. 配置更新（upsert + 脱敏值跳过 + 热更新 Settings）
4. 连接测试（未配置 / 成功 / 异常语义化）
5. 启动时加载（apply_config_to_settings 覆盖 Settings 单例）
"""
import pytest
from unittest.mock import AsyncMock

from app.services.cos_config_service import CosConfigService, _mask_key


@pytest.fixture(autouse=True)
def reset_cos_settings(monkeypatch):
    """每个测试前复位 Settings 单例的 COS 字段，隔离 update_config /
    apply_config_to_settings 对全局单例的副作用污染。monkeypatch 在测试后自动还原。"""
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "")
    monkeypatch.setattr(s, "COS_BUCKET", "")
    monkeypatch.setattr(s, "COS_REGION", "ap-guangzhou")
    monkeypatch.setattr(s, "COS_CDN_DOMAIN", "")


def test_mask_key_format():
    assert _mask_key("") == ""
    assert _mask_key("AKID1234") == "****1234"
    assert _mask_key("ab") == "****"


async def test_get_config_defaults(db_session):
    svc = CosConfigService(db_session)
    data = await svc.get_config_for_frontend()
    assert data["configured"] is False
    assert data["secret_id"] == ""
    assert data["secret_key"] == ""
    assert data["region"] == "ap-guangzhou"
    assert data["bucket"] == ""
    assert data["cdn_domain"] == ""


async def test_get_config_masks_secrets(db_session):
    svc = CosConfigService(db_session)
    await svc.update_config(
        secret_id="AKIDsecretlong",
        secret_key="sksecretlong",
        region="ap-shanghai",
        bucket="mybucket",
        cdn_domain="https://cdn.example.com",
    )
    data = await svc.get_config_for_frontend()
    assert data["configured"] is True
    assert data["secret_id"] == "****long"
    assert data["secret_key"] == "****long"
    assert data["region"] == "ap-shanghai"
    assert data["bucket"] == "mybucket"
    assert data["cdn_domain"] == "https://cdn.example.com"


async def test_update_config_skips_masked_secret(db_session):
    svc = CosConfigService(db_session)
    # 首次写入真实凭证
    await svc.update_config(secret_id="AKIDreal", secret_key="skreal", bucket="b")
    # 回传脱敏值：应视为未修改，保留库中明文
    await svc.update_config(
        secret_id="****real", secret_key="****real", region="ap-shanghai"
    )
    data = await svc.get_config_for_frontend()
    assert data["secret_id"] == "****real"
    assert data["secret_key"] == "****real"
    assert data["region"] == "ap-shanghai"
    # 原始明文仍在库里
    assert await svc.get_config_value("cos_secret_id") == "AKIDreal"
    assert await svc.get_config_value("cos_secret_key") == "skreal"


async def test_test_connection_not_configured(db_session, monkeypatch):
    import app.cos.client as cos_client_mod

    monkeypatch.setattr(cos_client_mod, "is_cos_configured", lambda: False)
    svc = CosConfigService(db_session)
    result = await svc.test_connection()
    assert result["success"] is False
    assert "未配置" in result["message"]


async def test_test_connection_success(db_session, monkeypatch):
    import app.cos.client as cos_client_mod

    monkeypatch.setattr(cos_client_mod, "is_cos_configured", lambda: True)
    fake = AsyncMock()
    fake.list_objects_delimited = AsyncMock(
        return_value={"Contents": [], "CommonPrefixes": []}
    )
    monkeypatch.setattr(cos_client_mod, "cos_client", fake)

    svc = CosConfigService(db_session)
    result = await svc.test_connection()
    assert result["success"] is True
    assert result["message"] == "连接成功"


async def test_test_connection_error_semantic(db_session, monkeypatch):
    import app.cos.client as cos_client_mod

    monkeypatch.setattr(cos_client_mod, "is_cos_configured", lambda: True)
    fake = AsyncMock()
    fake.list_objects_delimited = AsyncMock(
        side_effect=Exception("AccessDenied for bucket")
    )
    monkeypatch.setattr(cos_client_mod, "cos_client", fake)

    svc = CosConfigService(db_session)
    result = await svc.test_connection()
    assert result["success"] is False
    assert "AccessDenied" in result["message"]


async def test_apply_config_to_settings(db_session, monkeypatch):
    from app.config import get_settings

    s = get_settings()
    # 先把 Settings 单例清回默认（模拟进程刚启动）
    monkeypatch.setattr(s, "COS_SECRET_ID", "")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "")
    monkeypatch.setattr(s, "COS_BUCKET", "")
    monkeypatch.setattr(s, "COS_REGION", "ap-guangzhou")
    monkeypatch.setattr(s, "COS_CDN_DOMAIN", "")

    svc = CosConfigService(db_session)
    await svc.update_config(
        secret_id="AKIDx", secret_key="skx", bucket="bkt", region="ap-beijing"
    )

    # 重新加载（模拟 lifespan 启动）
    svc2 = CosConfigService(db_session)
    await svc2.apply_config_to_settings()
    assert s.COS_SECRET_ID == "AKIDx"
    assert s.COS_SECRET_KEY == "skx"
    assert s.COS_BUCKET == "bkt"
    assert s.COS_REGION == "ap-beijing"
