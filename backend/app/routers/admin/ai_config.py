"""B 端 AI 服务配置路由。

端点：
- GET  /admin/api/v1/ai/config     获取配置（API Key 脱敏）
- PUT  /admin/api/v1/ai/config     保存配置（热更新，含预设配置同步）
- POST /admin/api/v1/ai/test-llm   测试 LLM 连接
- POST /admin/api/v1/ai/test-tts   测试 TTS 连接
- POST /admin/api/v1/ai/preview-tts  TTS 试音（用当前表单参数合成测试音频）
- GET  /admin/api/v1/ai/usage      用量统计（历史，来自 DB）
- GET  /admin/api/v1/ai/budget     实时预算摘要（来自内存，含限额信息）
- GET  /admin/api/v1/ai/presets    LLM 提供商预设
- GET  /admin/api/v1/ai/voices     TTS 音色列表
- POST /admin/api/v1/ai/reset-config  恢复 LLM 初始配置（清空预设配置）

所有端点需要管理员权限，防止运营误改 AI 配置。
"""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_budget import get_today_summary, reset_budget
from app.core.auth import require_admin, AdminPayload
from app.core.response import error, success
from app.database import get_db
from app.services.ai_config_service import AIConfigService

router = APIRouter(prefix="/admin/api/v1/ai", tags=["B端-AI服务"])


class LLMConfigBody(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout_sec: int = 30
    retry_attempts: int = 3
    target_duration_sec: int = 600
    segment_gap_sec: float = 0.5


class TTSConfigBody(BaseModel):
    # Provider 选择（aliyun/edge/tencent）
    provider: str = "aliyun"
    # 阿里云 NLS 字段
    api_key: str = ""
    appkey: str = ""
    voice: str = "xiaoyun"
    sample_rate: int = 44100
    format: str = "mp3"
    timeout_sec: int = 60
    retry_attempts: int = 3
    # 阿里云 TTS 音量/语速/基频（NLS tts_request 参数）
    aliyun_volume: int = 50
    aliyun_speech_rate: int = 0
    aliyun_pitch_rate: int = 0
    # Edge-TTS 字段
    edge_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_rate: str = ""
    edge_volume: str = ""
    edge_pitch: str = ""
    # 腾讯云 TTS 字段
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_region: str = "ap-guangzhou"
    tencent_voice_type: int = 101011
    tencent_volume: int = 0
    tencent_speed: int = 0


class SaveConfigBody(BaseModel):
    llm: LLMConfigBody
    tts: TTSConfigBody
    # 当前选中的 LLM 预设 key（用于同步保存预设配置，空字符串表示未选择预设）
    selected_preset: str = ""


class TestLLMBody(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class TestTTSBody(BaseModel):
    provider: str = "aliyun"
    # 阿里云
    api_key: str = ""
    appkey: str = ""
    # Edge-TTS
    edge_voice: str = ""
    # 腾讯云
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_region: str = ""
    tencent_voice_type: int = 0


class PreviewTTSBody(BaseModel):
    """试音请求体：携带当前表单参数（不依赖已保存配置），合成测试文本。"""
    provider: str = "edge"
    text: str = ""
    # 阿里云
    aliyun_api_key: str = ""
    aliyun_appkey: str = ""
    aliyun_voice: str = ""
    aliyun_volume: int = 50
    aliyun_speech_rate: int = 0
    aliyun_pitch_rate: int = 0
    # Edge-TTS
    edge_voice: str = ""
    edge_rate: str = ""
    edge_volume: str = ""
    edge_pitch: str = ""
    # 腾讯云
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_region: str = ""
    tencent_voice_type: int = 0
    tencent_volume: int = 0
    tencent_speed: int = 0


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取 AI 配置（API Key 脱敏）。

    返回的 llm.preset_configs 为每个预设独立保存的配置（API Key 脱敏），
    llm.selected_preset 为根据 base_url 反向匹配的当前预设 key。
    """
    svc = AIConfigService(db)
    data = await svc.get_config_for_frontend()
    return success(data=data)


@router.put("/config")
async def save_config(
    body: SaveConfigBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """保存 AI 配置（热更新 Settings 单例）。

    当 selected_preset 非空时，同步将当前 LLM 配置保存到预设配置 JSON，
    实现切换预设时返显之前保存的 API Key/Base URL/Model。
    """
    svc = AIConfigService(db)
    await svc.update_config(
        llm_config=body.llm.model_dump(),
        tts_config=body.tts.model_dump(),
        selected_preset=body.selected_preset,
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
    """测试 TTS 连接（按 provider 分支：阿里云鉴权 / Edge-TTS 合成 / 腾讯云合成）。"""
    svc = AIConfigService(db)
    result = await svc.test_tts_connection(
        provider=body.provider,
        api_key=body.api_key,
        appkey=body.appkey,
        edge_voice=body.edge_voice,
        tencent_secret_id=body.tencent_secret_id,
        tencent_secret_key=body.tencent_secret_key,
        tencent_region=body.tencent_region,
        tencent_voice_type=body.tencent_voice_type,
    )
    return success(data=result)


@router.post("/preview-tts")
async def preview_tts(
    body: PreviewTTSBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """试音：用当前表单参数合成测试文本，返回音频二进制供前端播放。

    与 /test-tts 区别：测试连接只验证鉴权返回 JSON 结果，试音返回实际
    MP3 音频流。用户调整音量/语速/基频后无需保存即可试听效果。
    """
    svc = AIConfigService(db)
    try:
        audio = await svc.preview_tts(
            text=body.text,
            provider=body.provider,
            aliyun_api_key=body.aliyun_api_key,
            aliyun_appkey=body.aliyun_appkey,
            aliyun_voice=body.aliyun_voice,
            aliyun_volume=body.aliyun_volume,
            aliyun_speech_rate=body.aliyun_speech_rate,
            aliyun_pitch_rate=body.aliyun_pitch_rate,
            edge_voice=body.edge_voice,
            edge_rate=body.edge_rate,
            edge_volume=body.edge_volume,
            edge_pitch=body.edge_pitch,
            tencent_secret_id=body.tencent_secret_id,
            tencent_secret_key=body.tencent_secret_key,
            tencent_region=body.tencent_region,
            tencent_voice_type=body.tencent_voice_type,
            tencent_volume=body.tencent_volume,
            tencent_speed=body.tencent_speed,
        )
    except ValueError as e:
        return error(400, str(e), http_status=400)
    except Exception as e:
        return error(500, f"试音合成失败: {e}", http_status=500)

    return Response(content=audio, media_type="audio/mpeg")


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


@router.post("/reset-config")
async def reset_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """恢复 LLM 初始配置（清空用户保存的预设配置和当前 LLM 配置）。

    清空 llm_api_key / llm_base_url / llm_model / llm_preset_configs，
    保留 timeout/retry 等通用项。热更新 Settings 单例回退到 .env 默认值。
    返回重置后的 LLM 配置供前端刷新表单。
    """
    svc = AIConfigService(db)
    llm_config = await svc.reset_to_defaults()
    return success(data={"llm": llm_config}, message="LLM 配置已恢复初始状态")


@router.get("/presets")
async def get_presets(
    admin: AdminPayload = Depends(require_admin),
):
    """获取 LLM 提供商预设列表。"""
    svc = AIConfigService.__new__(AIConfigService)
    return success(data=svc.get_presets())


@router.get("/voices")
async def get_voices(
    provider: str = None,
    admin: AdminPayload = Depends(require_admin),
):
    """获取 TTS 音色列表（按 provider 返回不同音色体系）。"""
    svc = AIConfigService.__new__(AIConfigService)
    return success(data=svc.get_voices(provider))
