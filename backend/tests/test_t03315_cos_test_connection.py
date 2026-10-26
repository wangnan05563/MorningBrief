"""T03315：COS「测试连接」必须走包装层的小写参数名。

原缺陷：`test_connection` 用 SDK 风格的大写关键字调用 `list_objects_delimited`，
而包装层签名是全小写（`prefix/delimiter/marker/max_keys`）。Python 在进入函数体前
就抛 TypeError，被 `except Exception` 兜成「连接失败: …unexpected keyword argument」，
于是凭证与桶都正确时也报失败。旧用例用 AsyncMock 替换包装层，接受任意关键字，
所以一直是绿的。

这里把断言下移到 SDK 边界：只 patch `_get_cos_client`，让真实的包装层跑一遍。
"""
import pytest

from app.cos import client as cos_client_mod
from app.services.cos_config_service import CosConfigService


@pytest.fixture
def cos_configured(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "COS_SECRET_ID", "AKIDx")
    monkeypatch.setattr(s, "COS_SECRET_KEY", "skx")
    monkeypatch.setattr(s, "COS_BUCKET", "bkt")
    monkeypatch.setattr(s, "COS_REGION", "ap-guangzhou")
    return s


class FakeSdkClient:
    """只记录 kwargs 的假 CosS3Client，用来验证包装层转发的参数名与取值。"""

    def __init__(self, error: Exception | None = None):
        self.calls: list[dict] = []
        self.error = error

    def list_objects(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"Contents": [], "CommonPrefixes": [], "IsTruncated": False}


async def test_test_connection_succeeds_and_forwards_lowercase_kwargs(cos_configured, monkeypatch):
    """凭证有效时必须返回 success=True，且 SDK 收到的仍是 SDK 要求的参数名。"""
    fake = FakeSdkClient()
    monkeypatch.setattr(cos_client_mod, "_get_cos_client", lambda: fake)

    result = await CosConfigService(None).test_connection()

    assert result["success"] is True, result
    assert result["message"] == "连接成功"
    assert fake.calls == [{"Bucket": "bkt", "Prefix": "", "Delimiter": "/", "MaxKeys": 1}]


async def test_test_connection_maps_access_denied(cos_configured, monkeypatch):
    """真实 SDK 抛权限错误时仍走语义化提示，别被本次修正影响。"""
    fake = FakeSdkClient(error=RuntimeError("AccessDenied"))
    monkeypatch.setattr(cos_client_mod, "_get_cos_client", lambda: fake)

    result = await CosConfigService(None).test_connection()

    assert result["success"] is False
    assert result["message"] == "凭证无效或无 Bucket 访问权限（AccessDenied）"
