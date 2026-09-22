"""升级服务单元测试（T00879：桌面端一键更新包下载与安装）。

覆盖：
- pick_release_asset：GitHub 资产/缓存字段两种来源下的安装器（.exe）挑选
- _run_upgrade 开发模式：下载后收敛为 dev_staged（不拉起真实安装器）
- _run_upgrade 失败路径：下载异常收敛为 error（可重试）

设计说明：
- 升级状态为模块级单例，测试前必须 _reset_upgrade_for_test 保证隔离（规则 89）。
- 开发模式不真实启动安装器，仅停留 dev_staged，便于本地验证下载产物。
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services import upgrade_service as us
from app.services.upgrade_service import pick_release_asset


# ====================== pick_release_asset ======================

def test_pick_asset_hits_installer_exe():
    """含关键字且以 .exe 结尾的安装器被选中。"""
    release = {"assets": [
        {"name": "MorningBrief-Setup-v1.2.3.exe", "size": 1024,
         "browser_download_url": "https://x/MorningBrief-Setup-v1.2.3.exe"},
    ]}
    asset = pick_release_asset(release)
    assert asset is not None
    assert asset["name"] == "MorningBrief-Setup-v1.2.3.exe"
    assert asset["size_bytes"] == 1024
    assert asset["download_url"].endswith(".exe")
    assert asset["type"] == "installer"


def test_pick_asset_skips_non_exe_and_unrelated():
    """源码包（tar.gz）与不含关键字的 exe 都不能作为更新包。"""
    release = {"assets": [
        {"name": "MorningBrief-Setup-v1.2.3.tar.gz", "size": 1,
         "browser_download_url": "https://x/a.tar.gz"},
        {"name": "OtherSetup-v1.exe", "size": 2,
         "browser_download_url": "https://x/other.exe"},
    ]}
    assert pick_release_asset(release) is None


def test_pick_asset_supports_cached_fields():
    """兼容本服务缓存后的字段名（name/size_bytes/download_url）。"""
    release = {"assets": [
        {"name": "MorningBrief-Setup-v1.exe", "size_bytes": 2048,
         "download_url": "https://x/mb.exe"},
    ]}
    asset = pick_release_asset(release)
    assert asset is not None
    assert asset["size_bytes"] == 2048
    assert asset["download_url"] == "https://x/mb.exe"


def test_pick_asset_none_without_assets():
    """无 assets 时返回 None。"""
    assert pick_release_asset({}) is None


# ====================== 开发模式升级流程 ======================

@pytest.mark.asyncio
async def test_run_upgrade_develop_mode_staged():
    """开发模式：下载后停在 dev_staged，不启动安装器。

    为什么断言 dev_staged 而非启动：开发 env 无真实安装器，强行走启动会
    弹出无关 GUI，故仅留下载产物供人工核验。
    """
    us._reset_upgrade_for_test()
    asset = {"name": "MorningBrief-Setup-v1.1.0.exe", "size_bytes": 0,
             "download_url": "https://x/a.exe", "type": "installer"}
    with patch.object(us, "is_frozen", return_value=False), \
         patch.object(us, "get_app_root", return_value=Path("/tmp/fake-app")), \
         patch.object(us, "_download_release", new=AsyncMock()):
        await us.start_upgrade("v1.1.0", asset)
        await asyncio.wait_for(us._UPGRADE_TASK, timeout=5)
    state = us.get_upgrade_state()
    assert state["state"] == "dev_staged"
    assert "开发模式" in state["message"]
    assert state["error"] == ""


@pytest.mark.asyncio
async def test_run_upgrade_launches_installer_when_frozen():
    """打包模式：下载后启动安装器并置 restarting。"""
    us._reset_upgrade_for_test()
    asset = {"name": "MorningBrief-Setup-v1.1.0.exe", "size_bytes": 0,
             "download_url": "https://x/a.exe", "type": "installer"}
    with patch.object(us, "is_frozen", return_value=True), \
         patch.object(us, "get_app_root", return_value=Path("C:/fake-app")), \
         patch.object(us, "_download_release", new=AsyncMock()), \
         patch.object(us, "_launch_installer") as mock_launch:
        await us.start_upgrade("v1.1.0", asset)
        await asyncio.wait_for(us._UPGRADE_TASK, timeout=5)
    state = us.get_upgrade_state()
    assert state["state"] == "restarting"
    assert "安装器已启动" in state["message"]
    mock_launch.assert_called_once()


@pytest.mark.asyncio
async def test_run_upgrade_download_failure_sets_error():
    """下载异常收敛为 error 并入 error 信息，供前端展示重试。"""
    us._reset_upgrade_for_test()
    asset = {"name": "MorningBrief-Setup-v1.1.0.exe", "size_bytes": 0,
             "download_url": "https://x/a.exe", "type": "installer"}
    with patch.object(us, "is_frozen", return_value=False), \
         patch.object(us, "get_app_root", return_value=Path("/tmp/fake-app")), \
         patch.object(us, "_download_release",
                      new=AsyncMock(side_effect=RuntimeError("网络中断"))):
        await us.start_upgrade("v1.1.0", asset)
        await asyncio.wait_for(us._UPGRADE_TASK, timeout=5)
    state = us.get_upgrade_state()
    assert state["state"] == "error"
    assert "网络中断" in state["error"]


@pytest.mark.asyncio
async def test_start_upgrade_rejects_missing_download_url():
    """资产缺少下载地址时拒绝启动并抛出可读错误。"""
    us._reset_upgrade_for_test()
    with pytest.raises(ValueError):
        await us.start_upgrade("v1.1.0", {"name": "a.exe", "size_bytes": 0})