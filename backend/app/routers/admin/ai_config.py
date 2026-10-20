"""B 端 AI 服务配置路由。

端点：
- GET  /admin/api/v1/ai/config     获取配置（API Key 脱敏）
- PUT  /admin/api/v1/ai/config     保存配置（热更新，含预设配置同步）
- GET  /admin/api/v1/ai/audio-profile 只读展示当前生效音频档位（码率+采样率套餐）
- POST /admin/api/v1/ai/test-llm   测试 LLM 连接
- POST /admin/api/v1/ai/test-tts   测试 TTS 连接
- POST /admin/api/v1/ai/preview-tts  TTS 试音（用当前表单参数合成测试音频）
- POST /admin/api/v1/ai/download-tts-models 触发下载本地离线 TTS 模型（Kokoro/Piper）
- GET  /admin/api/v1/ai/download-tts-models/status 查询下载进度（前端轮询）
- GET  /admin/api/v1/ai/usage      用量统计（历史，来自 DB）
- GET  /admin/api/v1/ai/budget     实时预算摘要（来自内存，含限额信息）
- GET  /admin/api/v1/ai/presets    LLM 提供商预设
- GET  /admin/api/v1/ai/voices     TTS 音色列表（优先官方同步缓存）
- GET  /admin/api/v1/ai/voices/meta  音色列表同步元信息（is_custom/synced_at/count）
- POST /admin/api/v1/ai/voices/sync  同步官方最新音色并持久化（edge/tencent）
- DELETE /admin/api/v1/ai/voices/sync  清除同步缓存，回退内置清单
- POST /admin/api/v1/ai/models     拉取可用模型列表（OpenAI 兼容 /models）
- POST /admin/api/v1/ai/chat       知识库问答（指定模型发起对话）
- GET  /admin/api/v1/ai/selected-model  获取默认模型
- POST /admin/api/v1/ai/selected-model  保存默认模型
- POST /admin/api/v1/ai/reset-config  恢复 LLM 初始配置（清空预设配置）

所有端点需要管理员权限，防止运营误改 AI 配置。
"""
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_budget import get_today_summary, reset_budget
from app.core.audio_profile import AUDIO_PROFILES, resolve_encoding
from app.core.auth import require_admin, AdminPayload
from app.core.response import error, success
from app.config import get_settings
from app.database import get_db
from app.services.ai_config_service import AIConfigService
from app.services.tts_model_manager import get_download_status, run_download

router = APIRouter(prefix="/admin/api/v1/ai", tags=["B端-AI服务"])


class LLMConfigBody(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout_sec: int = 30
    # 知识库问答超时（FR-UX-701 / T02515）：必须在这里声明——本 body 是逐字段白名单，
    # 没声明的键会被 pydantic 静默丢掉（T01729 的 llm_max_script_segments 就是这么坏的）。
    chat_timeout_sec: int = 120
    retry_attempts: int = 3
    target_duration_sec: int = 600
    segment_gap_sec: float = 0.5
    # 单期节目最大段数上限（T01729：30 分钟听书档热调 18~20，默认 10）
    llm_max_script_segments: int = 10


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
    # Kokoro TTS 字段（本地离线，免费高质量）
    kokoro_lang: str = "z"
    kokoro_voice: str = "zf_xiaoxiao"
    kokoro_speed: float = 1.0
    # Piper TTS 字段（本地离线，轻量免费）
    piper_voice: str = "zh_CN-huayan-medium"
    piper_voice_dir: str = "./models/piper"
    piper_length_scale: float = 1.0
    piper_volume: float = 0.5
    piper_noise_scale: float = 0.667
    # TTS 交叉音色（段落间轮流换声，避免同质化）
    # 结构：{"enabled": bool, "strategy": "round_robin"|"random"|"interval",
    # "interval": int, "voices": {provider: [voice_key, ...]}}
    cross_voice: Optional[dict] = None


class ImageConfigBody(BaseModel):
    """图片生成配置（T00730：频道图标 AI 生成服务）。"""
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class SaveConfigBody(BaseModel):
    llm: LLMConfigBody
    tts: TTSConfigBody
    # 当前选中的 LLM 预设 key（用于同步保存预设配置，空字符串表示未选择预设）
    selected_preset: str = ""
    # 图片生成配置（可选段：旧前端不传时跳过，保持向后兼容）
    image: Optional[ImageConfigBody] = None


class VoiceSyncBody(BaseModel):
    """T00388 音色同步请求体：目标 TTS 引擎（edge/tencent）。"""

    provider: str


class TestLLMBody(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class TestImageBody(BaseModel):
    """图片服务连接测试（T00730）：携带表单值，空值回退已保存配置。"""
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
    # Kokoro
    kokoro_lang: str = ""
    kokoro_voice: str = ""
    # Piper
    piper_voice: str = ""
    piper_voice_dir: str = ""


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
    # Kokoro
    kokoro_lang: str = ""
    kokoro_voice: str = ""
    kokoro_speed: float = 0.0
    # Piper
    piper_voice: str = ""
    piper_voice_dir: str = ""
    piper_length_scale: float = 0.0
    piper_volume: float = 0.0
    piper_noise_scale: float = 0.0


class DownloadTTSModelsBody(BaseModel):
    """触发下载 TTS 模型（Kokoro/Piper 本地离线引擎）。

    仅支持 kokoro / piper 两个本地引擎；其他 provider 无需下载模型。
    字段透传当前表单值，独立于已保存配置。
    """
    provider: str = "piper"
    # Kokoro 参数
    kokoro_lang: str = ""
    kokoro_voice: str = ""
    # Piper 参数
    piper_voice: str = ""
    piper_voice_dir: str = "./models/piper"


class FetchModelsBody(BaseModel):
    """拉取可用模型列表：base_url / api_key 可留空，留空时使用已保存配置。

    base_url / api_key 与「LLM 大模型」配置一致；前端透传配置的 base_url，
    API Key 因脱敏不回传，由后端从已保存明文解析。
    """
    base_url: str = ""
    api_key: str = ""


class ChatBody(BaseModel):
    """知识库问答：携带当前选中的模型与对话历史。

    messages 为 OpenAI 格式：[{"role": "user"|"assistant", "content": "..."}]
    base_url / api_key 可留空，留空时使用已保存配置。
    """
    model: str = ""
    messages: list[dict] = []
    base_url: str = ""
    api_key: str = ""


class SelectedModelBody(BaseModel):
    """保存/读取用户最后选择的默认模型。"""
    model: str = ""


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
        image_config=body.image.model_dump() if body.image is not None else None,
    )
    return success(message="配置已保存")


@router.get("/audio-profile")
async def get_audio_profile(
    admin: AdminPayload = Depends(require_admin),
):
    """只读展示当前生效的音频档位（码率 + 采样率套餐，T01871）。

    故意不提供写接口：档位决定「已发布成品能不能播、听起来如何」，而 24kHz/AAC
    这类候选档位的真机兼容与人工试听尚未收口，管理端能改就等于让人误配置成
    不可播的成品；这里只回答「现在整条链路到底在用哪一组参数」。
    """
    enc = resolve_encoding(get_settings())
    return success(
        data={
            "profile": enc.profile,
            "label": enc.label,
            "bitrate": enc.bitrate,
            "sample_rate": enc.sample_rate,
            # 运营用 AUDIO_BITRATE / AUDIO_SAMPLE_RATE 显式覆盖时为 true，
            # 此时 profile/label 只是「基于哪个档位」，实际参数看上面两个字段
            "overridden": enc.overridden,
            "pcm_kb_per_sec": enc.pcm_kb_per_sec,
            "profiles": [
                {
                    "profile": key,
                    "label": val["label"],
                    "bitrate": val["bitrate"],
                    "sample_rate": val["sample_rate"],
                    "pcm_kb_per_sec": val["sample_rate"] * 2 // 1000,
                }
                for key, val in AUDIO_PROFILES.items()
            ],
        }
    )


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


@router.post("/test-image")
async def test_image(
    body: TestImageBody,
    admin: AdminPayload = Depends(require_admin),
):
    """图片生成服务连接测试（T00730：GET {base}/models 轻量探测，不消耗生成配额）。"""
    from app.services.image_gen_service import test_connection
    result = test_connection(
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
        kokoro_lang=body.kokoro_lang,
        kokoro_voice=body.kokoro_voice,
        piper_voice=body.piper_voice,
        piper_voice_dir=body.piper_voice_dir,
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
            kokoro_lang=body.kokoro_lang,
            kokoro_voice=body.kokoro_voice,
            kokoro_speed=body.kokoro_speed,
            piper_voice=body.piper_voice,
            piper_voice_dir=body.piper_voice_dir,
            piper_length_scale=body.piper_length_scale,
            piper_volume=body.piper_volume,
            piper_noise_scale=body.piper_noise_scale,
        )
    except ValueError as e:
        return error(400, str(e), http_status=400)
    except Exception as e:
        return error(500, f"试音合成失败: {e}", http_status=500)

    return Response(content=audio, media_type="audio/mpeg")


@router.post("/download-tts-models")
async def download_tts_models(
    body: DownloadTTSModelsBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """触发下载本地离线 TTS 模型（Kokoro / Piper）。

    模型下载耗时较长（Piper 几十~上百 MB，Kokoro 权重 ~165MB），接口立即返回
    「已启动」，实际下载在后台任务执行，前端通过 /download-tts-models/status
    轮询进度。

    仅 kokoro / piper 需要下载；其他 provider 返回错误提示。
    """
    provider = body.provider
    if provider not in ("kokoro", "piper"):
        return error(400, f"provider={provider} 无需下载模型（仅 kokoro/piper 为本地离线引擎）", http_status=400)

    # 后台触发下载（接口立即返回）
    background_tasks.add_task(
        run_download,
        provider,
        kokoro_lang=body.kokoro_lang,
        kokoro_voice=body.kokoro_voice,
        piper_voice=body.piper_voice,
        piper_voice_dir=body.piper_voice_dir,
    )
    return success(
        data={"provider": provider, "started": True},
        message=f"{provider} 模型下载已启动，请在页面查看进度",
    )


@router.get("/download-tts-models/status")
async def download_tts_models_status(
    provider: str = "piper",
    admin: AdminPayload = Depends(require_admin),
):
    """查询 TTS 模型下载状态（前端轮询）。

    返回 {status, message, progress, updated_at}，status ∈
    idle | downloading | success | failed。
    """
    return success(data=get_download_status(provider))


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
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取 TTS 音色列表（按 provider 返回不同音色体系）。

    优先返回官方接口同步缓存（T00388），无缓存时返回内置静态清单。
    """
    svc = AIConfigService(db)
    return success(data=await svc.get_voices_cached(provider))


@router.get("/voices/meta")
async def get_voices_meta(
    provider: str = None,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取音色列表同步元信息（是否官方同步 / synced_at / 数量 / 来源）。"""
    svc = AIConfigService(db)
    return success(data=await svc.get_voice_meta(provider))


@router.post("/voices/sync")
async def sync_voices(
    body: VoiceSyncBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """同步官方最新音色列表并持久化（T00388）。

    支持引擎：edge（微软官方目录）/ tencent（DescribeVoices，TC3 签名）。
    aliyun/kokoro/piper 无公开官方列表接口，明确报错，不做伪同步。
    同步成功后 get_voices_cached 优先返回缓存列表。
    """
    svc = AIConfigService(db)
    return success(data=await svc.sync_voices(body.provider))


@router.delete("/voices/sync")
async def reset_voices_cache(
    provider: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """清除音色同步缓存，回退内置静态清单（同步结果异常时的逃生口）。"""
    svc = AIConfigService(db)
    return success(data=await svc.reset_voices_cache(provider))


@router.post("/models")
async def fetch_models(
    body: FetchModelsBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """拉取可用模型列表（OpenAI 兼容 /models 接口）。

    根据 base_url + api_key 自动请求并解析模型列表；明确区分 base_url 不可达 /
    API Key 无效(401) / 返回内容无法解析等错误，返回可读 message。
    """
    svc = AIConfigService(db)
    result = await svc.fetch_llm_models(
        base_url=body.base_url,
        api_key=body.api_key,
    )
    return success(data=result)


@router.post("/chat")
async def chat(
    body: ChatBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """知识库问答：用指定模型发起一轮对话（OpenAI 兼容 chat/completions）。

    支持在问答过程中随时切换 model 参数（前端每次请求传入当前选中模型），
    切换立即生效。返回模型回复与 token 用量。

    超时口径（FR-UX-701 / T02515）：本接口在 LLM_CHAT_TIMEOUT_SEC（默认 120s）到点时
    返回 success=false + timeout=true + 「可重试」文案，刻意早于前端的 130s，
    这样用户看到的是一句能重试的业务提示，而不是浏览器层面的网络错误。

    「停止生成」的真实边界：前端点停止只会中止浏览器侧请求，非流式调用无法从客户端
    取消上游模型任务——服务端仍会把这一轮跑完并计入用量。要真正做到「停止即停止并
    停止计费」，得改成 SSE 流式（属 FR-UX-702 的范围），此处如实注释以免后来者误以为
    已经断开。
    """
    svc = AIConfigService(db)
    result = await svc.chat_with_model(
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
        messages=body.messages,
    )
    return success(data=result)


@router.get("/selected-model")
async def get_selected_model(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取用户最后选择的默认模型。"""
    svc = AIConfigService(db)
    return success(data={"model": await svc.get_selected_model()})


@router.post("/selected-model")
async def set_selected_model(
    body: SelectedModelBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """保存用户最后选择的模型为默认选项（下次自动选中）。"""
    svc = AIConfigService(db)
    await svc.set_selected_model(body.model)
    return success(message="已保存默认模型")
