"""TTS 模型下载管理器（Kokoro / Piper 本地离线引擎）。

为什么需要：
Kokoro 与 Piper 是本地离线免费 TTS 引擎，但首次使用需要获取模型权重 / 模型文件：
- Piper：语音模型为 .onnx + .onnx.json 文件，需从 HuggingFace 下载到 PIPER_VOICE_DIR
- Kokoro：模型权重由 kokoro.KPipeline 在首次实例化时从 HuggingFace 下载并缓存

为让运维无需登录服务器、直接在 B 端「AI 配置页」触发下载，本模块提供：
- run_download(provider, **params)：执行下载（后台任务调用），实时更新进程内状态
- get_download_status(provider)：读取下载状态，供前端轮询

设计约束（与项目架构一致）：
- 单 worker（UVICORN_WORKERS=1）下，进程内 _DOWNLOAD_STATE 字典即可安全共享状态，
  无需 Redis/DB。
- 下载可能较慢（几十~几百 MB），由调用方用 FastAPI BackgroundTasks 异步触发，
  接口立即返回，前端轮询状态。
- Piper 下载优先用官方 `piper.download_voices` CLI（索引权威，支持任意 voice），
  若该包不可用则回退到 HuggingFace 直链下载（仅支持内置索引内的已知中文 voice）。
- 支持 HF_ENDPOINT 环境变量（如 https://hf-mirror.com）以适配网络受限环境。
"""
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import threading

import httpx

logger = logging.getLogger(__name__)

# ---- 进程内下载状态（单 worker 安全） ----
# 结构：{ provider: {status, message, progress, updated_at} }
# status: idle | downloading | success | failed
_DOWNLOAD_STATE: dict[str, dict] = {}
_STATE_LOCK = threading.Lock()

# ---- Piper 语音模型 HuggingFace 索引（仅内置已知中文 voice） ----
# 路径结构遵循 rhasspy/piper-voices 仓库：<lang>/<voice_lang>/<speaker>/<quality>/<voice>
# ref 用 v1.0.0 稳定标签（与 .env.example / 文档一致，避免 main 漂移）
PIPER_VOICE_REF = "v1.0.0"
PIPER_VOICE_INDEX: dict[str, str] = {
    "zh_CN-huayan-medium": "zh/zh_CN/huayan/medium/zh_CN-huayan-medium",
    "zh_CN-huayan-x_low": "zh/zh_CN/huayan/x_low/zh_CN-huayan-x_low",
    "zh_CN-chenyang-medium": "zh/zh_CN/chenyang/medium/zh_CN-chenyang-medium",
    "zh_CN-lessac-medium": "zh/zh_CN/lessac/medium/zh_CN-lessac-medium",
}


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _set_state(provider: str, **fields) -> None:
    """更新（合并）某 provider 的下载状态。"""
    with _STATE_LOCK:
        cur = _DOWNLOAD_STATE.setdefault(provider, {})
        cur.update(fields)
        cur["updated_at"] = _now_iso()


def get_download_status(provider: str) -> dict:
    """读取某 provider 的下载状态（供前端轮询）。

    未触发过时返回 idle 占位。
    """
    with _STATE_LOCK:
        st = dict(_DOWNLOAD_STATE.get(provider, {}))
    if not st:
        return {"status": "idle", "message": "尚未下载模型", "progress": None}
    return st


# ---- Piper 下载 ----

def _run_subprocess(cmd: list[str], timeout: int = 600) -> None:
    """同步运行子进程（在 to_thread 中调用），非零退出抛 RuntimeError。"""
    res = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
    )
    if res.returncode != 0:
        stderr = (res.stderr or res.stdout or "")[:500]
        raise RuntimeError(f"子进程失败(code={res.returncode}): {stderr}")


def _flatten_voice(voice_dir: str, voice: str) -> bool:
    """若 piper CLI 把模型放到了 voice_dir/<voice>/ 子目录，展平到 voice_dir/。

    返回是否最终在 voice_dir/<voice>.onnx 找到模型。
    """
    direct = os.path.join(voice_dir, f"{voice}.onnx")
    if os.path.isfile(direct):
        return True
    sub = os.path.join(voice_dir, voice)
    src = os.path.join(sub, f"{voice}.onnx")
    if os.path.isfile(src):
        shutil.move(src, direct)
        jsrc = os.path.join(sub, f"{voice}.onnx.json")
        jdst = os.path.join(voice_dir, f"{voice}.onnx.json")
        if os.path.isfile(jsrc):
            shutil.move(jsrc, jdst)
        try:
            os.rmdir(sub)
        except OSError:
            pass
        return True
    return False


async def _download_file(url: str, dest: str) -> None:
    """流式下载文件到 dest（httpx 异步）。"""
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code} 下载失败: {url}")
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(1024 * 64):
                    f.write(chunk)


async def _download_piper(voice: str, voice_dir: str) -> dict:
    """下载 Piper 语音模型。

    策略：
    1. 若 piper 包可用，优先用官方 `python -m piper.download_voices`（索引权威，支持任意 voice）
    2. 否则回退 HuggingFace 直链下载（仅内置索引内的已知中文 voice）
    """
    if not voice:
        return {"success": False, "message": "未指定 Piper 语音模型名（PIPER_VOICE）"}

    have_piper = False
    try:
        import piper  # noqa: F401
        have_piper = True
    except Exception:
        pass

    os.makedirs(voice_dir, exist_ok=True)

    # 策略 1：官方 CLI（支持任意 voice）
    if have_piper:
        _set_state(
            "piper", status="downloading",
            message=f"通过 piper CLI 下载 {voice} ...", progress=0.1,
        )
        try:
            await asyncio.to_thread(
                _run_subprocess,
                [sys.executable, "-m", "piper.download_voices",
                 "--data-dir", voice_dir, "--yes", voice],
            )
            if _flatten_voice(voice_dir, voice):
                return {
                    "success": True,
                    "message": f"Piper 模型 {voice} 下载完成（{voice_dir}）",
                }
            # CLI 执行但未在预期位置找到文件，继续回退 HTTP
            logger.warning("piper CLI 执行后未在 %s 找到 %s.onnx，回退 HTTP", voice_dir, voice)
        except Exception as e:
            logger.warning("piper CLI 下载失败，回退 HuggingFace 直链: %s", e)

    # 策略 2：HuggingFace 直链（仅内置索引内的已知 voice，不依赖 piper 包）
    if voice not in PIPER_VOICE_INDEX:
        return {
            "success": False,
            "message": (
                f"未在内置索引中找到 Piper 语音 {voice}，"
                f"请手动执行：python -m piper.download_voices {voice}"
            ),
        }

    base = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    prefix = f"{base}/rhasspy/piper-voices/resolve/{PIPER_VOICE_REF}/{PIPER_VOICE_INDEX[voice]}"
    onnx_url = f"{prefix}.onnx"
    json_url = f"{prefix}.onnx.json"

    _set_state("piper", status="downloading", message=f"下载 {voice}.onnx ...", progress=0.3)
    await _download_file(onnx_url, os.path.join(voice_dir, f"{voice}.onnx"))

    _set_state("piper", status="downloading", message=f"下载 {voice}.onnx.json ...", progress=0.8)
    await _download_file(json_url, os.path.join(voice_dir, f"{voice}.onnx.json"))

    _set_state("piper", status="downloading", message="校验文件 ...", progress=0.95)
    if not os.path.isfile(os.path.join(voice_dir, f"{voice}.onnx")):
        return {"success": False, "message": f"下载后未找到 {voice}.onnx，请检查网络或 HF_ENDPOINT"}

    return {"success": True, "message": f"Piper 模型 {voice} 下载完成 -> {voice_dir}"}


# ---- Kokoro 下载（预热触发 HF 权重下载） ----

async def _download_kokoro(lang: str, voice: str) -> dict:
    """预热 Kokoro 模型：首次实例化 KPipeline 会从 HuggingFace 下载并缓存权重。

    若 kokoro 包未安装，返回安装指引（模型权重无法在缺包情况下获取）。
    """
    try:
        from kokoro import KPipeline  # noqa: F401
    except Exception:
        return {
            "success": False,
            "message": "kokoro 包未安装，请先执行：pip install kokoro misaki[zh]",
        }

    lang = lang or "z"
    _set_state(
        "kokoro", status="downloading",
        message=f"加载 Kokoro 模型 lang={lang}（首次会从 HuggingFace 下载权重 ~165MB）...",
        progress=0.2,
    )
    try:
        # KPipeline 首次实例化会下载并缓存模型权重（中文 ~165MB），用 to_thread 避免阻塞事件循环
        await asyncio.to_thread(KPipeline, lang_code=lang)
    except Exception as e:
        return {"success": False, "message": f"Kokoro 模型加载/下载失败: {e}"}

    return {"success": True, "message": f"Kokoro 模型已就绪（lang={lang}）"}


# ---- 入口 ----

async def run_download(provider: str, **params) -> dict:
    """执行模型下载并更新进程内状态。

    由路由层通过 FastAPI BackgroundTasks 异步触发（接口立即返回，
    前端轮询 get_download_status 获取进度）。

    Args:
        provider: "kokoro" | "piper"
        params: 透传 kokoro_lang/kokoro_voice/piper_voice/piper_voice_dir
    """
    try:
        if provider == "piper":
            result = await _download_piper(
                params.get("piper_voice", ""),
                params.get("piper_voice_dir", "./models/piper"),
            )
        elif provider == "kokoro":
            result = await _download_kokoro(
                params.get("kokoro_lang", ""),
                params.get("kokoro_voice", ""),
            )
        else:
            result = {"success": False, "message": f"不支持的 provider: {provider}"}
    except Exception as e:
        logger.exception("TTS 模型下载异常 provider=%s", provider)
        result = {"success": False, "message": f"下载异常: {e}"}

    status = "success" if result.get("success") else "failed"
    _set_state(
        provider,
        status=status,
        message=result.get("message", ""),
        progress=1.0 if result.get("success") else None,
    )
    return result
