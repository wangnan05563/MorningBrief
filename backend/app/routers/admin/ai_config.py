"""B 端 AI 服务配置路由。

端点：
- GET  /admin/api/v1/ai/config     获取配置（API Key 脱敏）
- PUT  /admin/api/v1/ai/config     保存配置（热更新）
- POST /admin/api/v1/ai/test-llm   测试 LLM 连接
- POST /admin/api/v1/ai/test-tts   测试 TTS 连接
- GET  /admin/api/v1/ai/usage      用量统计（历史，来自 DB）
- GET  /admin/api/v1/ai/budget     实时预算摘要（来自内存，含限额信息）
- GET  /admin/api/v1/ai/presets    LLM 提供商预设
- GET  /admin/api/v1/ai/voices     TTS 音色列表

所有端点需要管理员权限，防止运营误改 AI 配置。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_budget import get_today_summary, reset_budget
from app.core.auth import require_admin, AdminPayload
from app.core.response import success
from app.database import get_db
from app.services.ai_config_service import AIConfigService

router = APIRouter(prefix="/admin/api/v1/ai", tags=["B端-AI服务"])


class LLMConfigBody(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout_sec: int = 30
    retry_attempts: int = 3


class TTSConfigBody(BaseModel):
    api_key: str = ""
    appkey: str = ""
    voice: str = "xiaoyun"
    sample_rate: int = 44100
    format: str = "mp3"
    timeout_sec: int = 60
    retry_attempts: int = 3


class SaveConfigBody(BaseModel):
    llm: LLMConfigBody
    tts: TTSConfigBody


class TestLLMBody(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class TestTTSBody(BaseModel):
    api_key: str = ""
    appkey: str = ""


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取 AI 配置（API Key 脱敏）。"""
    svc = AIConfigService(db)
    data = await svc.get_config_for_frontend()
    return success(data=data)


@router.put("/config")
async def save_config(
    body: SaveConfigBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """保存 AI 配置（热更新 Settings 单例）。"""
    svc = AIConfigService(db)
    await svc.update_config(
        llm_config=body.llm.model_dump(),
        tts_config=body.tts.model_dump(),
    )
    return success(message="配置已保存")


@router.post("/test-llm")
async def test_llm(
    body: TestLLMBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """测试 LLM 连接（发送最小化请求验证鉴权）。"""
    svc = AIConfigService(db)
    result = await svc.test_llm_connection(
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
    )
    return success(data=result)


@router.post("/test-tts")
async def test_tts(
    body: TestTTSBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """测试 TTS 连接（验证阿里云 NLS 鉴权）。"""
    svc = AIConfigService(db)
    result = await svc.test_tts_connection(
        api_key=body.api_key,
        appkey=body.appkey,
    )
    return success(data=result)


@router.get("/usage")
async def get_usage(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取 AI 用量统计（今日 + 7 天趋势）。"""
    svc = AIConfigService(db)
    data = await svc.get_usage_summary()
    return success(data=data)


@router.get("/budget")
async def get_budget(
    admin: AdminPayload = Depends(require_admin),
):
    """获取今日实时预算摘要（含已用额度与限额配置）。

    与 /usage 区别：/usage 查 DB 历史聚合，/budget 查内存实时计数，
    前端用量面板用此接口展示剩余额度与进度条。
    """
    data = get_today_summary()
    return success(data=data)


@router.post("/budget/reset")
async def reset_budget_endpoint(
    admin: AdminPayload = Depends(require_admin),
):
    """重置今日预算计数（运维应急用）。

    清空内存计数与持久化文件中的今日记录。
    用于预算误判（如测试调用被计入预算）后解锁。
    """
    reset_budget()
    return success(message="预算计数已重置")


@router.get("/presets")
async def get_presets(
    admin: AdminPayload = Depends(require_admin),
):
    """获取 LLM 提供商预设列表。"""
    svc = AIConfigService.__new__(AIConfigService)
    return success(data=svc.get_presets())


@router.get("/voices")
async def get_voices(
    admin: AdminPayload = Depends(require_admin),
):
    """获取 TTS 音色列表。"""
    svc = AIConfigService.__new__(AIConfigService)
    return success(data=svc.get_voices())
