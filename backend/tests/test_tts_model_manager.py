"""TTS 模型下载管理器测试（Kokoro / Piper）。

通过 monkeypatch 隔离外部依赖（httpx 下载 / kokoro / piper 包），
验证：Piper HuggingFace 直下成功、未知 voice 报错、Kokoro 预热成功、
Kokoro 缺包报错、状态机跟踪。
"""
import asyncio
import os
import sys
import types

import pytest

from app.services import tts_model_manager as mgr


@pytest.fixture(autouse=True)
def _clear_state():
    """每个用例前清空进程内下载状态，避免用例间串扰。"""
    mgr._DOWNLOAD_STATE.clear()
    yield
    mgr._DOWNLOAD_STATE.clear()


async def _fake_download(url: str, dest: str):
    """替代 _download_file：直接写占位字节，模拟下载完成。"""
    with open(dest, "wb") as f:
        f.write(b"FAKE_MODEL_BYTES")


def test_status_idle_before_download():
    st = mgr.get_download_status("piper")
    assert st["status"] == "idle"


def test_piper_http_download_success(tmp_path, monkeypatch):
    """Piper：走 HuggingFace 直链下载，落盘 .onnx + .onnx.json 并返回 success。"""
    # 确保 piper 包不可用，强制走 HTTP 直链分支
    # （pytest 无 delete；置 None 使 import piper 抛 ImportError，结束自动还原）
    monkeypatch.setitem(sys.modules, "piper", None)
    monkeypatch.setattr(mgr, "_download_file", _fake_download)

    voice_dir = str(tmp_path / "models" / "piper")
    result = asyncio.run(
        mgr.run_download("piper", piper_voice="zh_CN-huayan-medium", piper_voice_dir=voice_dir)
    )
    assert result["success"] is True
    assert os.path.isfile(os.path.join(voice_dir, "zh_CN-huayan-medium.onnx"))
    assert os.path.isfile(os.path.join(voice_dir, "zh_CN-huayan-medium.onnx.json"))

    st = mgr.get_download_status("piper")
    assert st["status"] == "success"
    assert st["progress"] == 1.0


def test_piper_unknown_voice_errors(tmp_path, monkeypatch):
    """Piper：未知 voice（不在内置索引）应报错，不触发下载。"""
    monkeypatch.setitem(sys.modules, "piper", None)
    monkeypatch.setattr(mgr, "_download_file", _fake_download)

    voice_dir = str(tmp_path / "models" / "piper")
    result = asyncio.run(
        mgr.run_download("piper", piper_voice="zh_CN-not-exist-x", piper_voice_dir=voice_dir)
    )
    assert result["success"] is False
    assert "未在内置索引" in result["message"]
    st = mgr.get_download_status("piper")
    assert st["status"] == "failed"


def test_kokoro_warmup_success(monkeypatch):
    """Kokoro：包可用时，KPipeline 实例化（预热）成功。"""
    fake_kokoro = types.SimpleNamespace(KPipeline=lambda **kwargs: None)
    monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)

    result = asyncio.run(mgr.run_download("kokoro", kokoro_lang="z", kokoro_voice="zf_xiaoxiao"))
    assert result["success"] is True
    st = mgr.get_download_status("kokoro")
    assert st["status"] == "success"


def test_kokoro_missing_package_errors(monkeypatch):
    """Kokoro：包未安装时，返回安装指引。"""
    monkeypatch.setitem(sys.modules, "kokoro", None)

    result = asyncio.run(mgr.run_download("kokoro", kokoro_lang="z"))
    assert result["success"] is False
    assert "pip install kokoro" in result["message"]
    st = mgr.get_download_status("kokoro")
    assert st["status"] == "failed"


def test_unsupported_provider_errors():
    """非本地引擎（如 edge）不应触发下载。"""
    result = asyncio.run(mgr.run_download("edge", kokoro_lang="z"))
    assert result["success"] is False
    assert "不支持的 provider" in result["message"]
