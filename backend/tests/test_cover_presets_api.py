"""预制封面列表接口测试（T00731 加固）。

覆盖点：
- 只列 channel_{id}.ext 图片，排除 channel_{id}_icon.ext 图标与无关文件
- url 为干净的 /channel-assets/... 路径（不含查询串，可原样落库 cover_url）
- mtime 为文件修改时间整秒值（前端缩略图据此加 ?v= 版本号，
  解决「封面重制替换后浏览器沿用旧图缓存」导致的不显示/显示旧图）
- 频道名映射；频道不存在时回退文件名；按 channel_id 升序；空目录返回空数组
"""
import os

import pytest

from app.routers.admin import channels as channels_router


@pytest.fixture
def asset_dir(tmp_path, monkeypatch):
    """把资产目录隔离到 tmp_path，避免污染开发态 backend/data/channel_assets。"""
    d = tmp_path / "channel_assets"
    d.mkdir()
    monkeypatch.setattr(channels_router, "resolve_channel_asset_dir", lambda: d)
    return d


@pytest.fixture
def stub_blacklist(monkeypatch):
    """登出黑名单恒 False（与 test_channel_icon 同款）。"""
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def _mk_channel(client, admin_token, name: str) -> int:
    resp = client.post(
        "/admin/api/v1/channels",
        json={"name": name, "channel_type": "news"},
        headers=_auth(admin_token),
    ).json()
    assert resp["code"] == 0, resp
    return resp["data"]["id"]


def _write(path, size: int = 2048, mtime: int | None = None):
    """写一个占位图片文件，可指定 mtime 让断言完全确定。"""
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * max(0, size - 4))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _get_presets(client, admin_token):
    resp = client.get(
        "/admin/api/v1/channels/cover-presets", headers=_auth(admin_token)
    ).json()
    assert resp["code"] == 0, resp
    return resp["data"]


def test_lists_cover_with_clean_url_and_mtime(client, admin_token, stub_blacklist, asset_dir):
    cid = _mk_channel(client, admin_token, "T00731 科技前沿")
    _write(asset_dir / f"channel_{cid}.jpg", size=4096, mtime=1_700_000_000)

    presets = _get_presets(client, admin_token)

    assert len(presets) == 1, presets
    item = presets[0]
    assert item["channel_id"] == cid
    assert item["name"] == "T00731 科技前沿"
    # url 必须干净：它会被直接写进频道 cover_url 落库
    assert item["url"] == f"/channel-assets/channel_{cid}.jpg"
    assert "?" not in item["url"]
    assert item["mtime"] == 1_700_000_000
    assert item["size_kb"] == 4.0


def test_mtime_tracks_file_replacement(client, admin_token, stub_blacklist, asset_dir):
    """同路径换图（封面重制）后 mtime 必须变化——前端 ?v= 版本号据此刷新缓存。"""
    cid = _mk_channel(client, admin_token, "T00731 换图频道")
    f = _write(asset_dir / f"channel_{cid}.jpg", mtime=1_700_000_000)
    first = _get_presets(client, admin_token)[0]["mtime"]

    _write(f, size=8192, mtime=1_700_000_900)
    second = _get_presets(client, admin_token)[0]["mtime"]

    assert second == 1_700_000_900
    assert second > first
    # url 不含版本号，两次完全一致（版本号只作用于缩略图展示层）
    assert _get_presets(client, admin_token)[0]["url"] == f"/channel-assets/channel_{cid}.jpg"


def test_excludes_icon_and_unrelated_files(client, admin_token, stub_blacklist, asset_dir):
    cid = _mk_channel(client, admin_token, "T00731 过滤频道")
    _write(asset_dir / f"channel_{cid}.jpg")
    _write(asset_dir / f"channel_{cid}_icon.png")   # 图标：不得混入封面列表
    _write(asset_dir / "notes.txt")                 # 非图片
    _write(asset_dir / "channel_abc.jpg")           # 非数字 id
    (asset_dir / "subdir").mkdir()                  # 目录

    presets = _get_presets(client, admin_token)

    assert [p["channel_id"] for p in presets] == [cid], presets


def test_accepts_webp_and_png_and_jpeg(client, admin_token, stub_blacklist, asset_dir):
    _write(asset_dir / "channel_1.webp")
    _write(asset_dir / "channel_2.png")
    _write(asset_dir / "channel_3.jpeg")

    ids = [p["channel_id"] for p in _get_presets(client, admin_token)]

    assert ids == [1, 2, 3]


def test_name_falls_back_to_filename_when_channel_missing(
    client, admin_token, stub_blacklist, asset_dir
):
    _write(asset_dir / "channel_999.jpg")

    presets = _get_presets(client, admin_token)

    assert presets[0]["name"] == "channel_999"


def test_sorted_by_channel_id_asc(client, admin_token, stub_blacklist, asset_dir):
    for cid in (10, 2, 3):
        _write(asset_dir / f"channel_{cid}.jpg")

    ids = [p["channel_id"] for p in _get_presets(client, admin_token)]

    assert ids == [2, 3, 10]


def test_empty_dir_returns_empty_list(client, admin_token, stub_blacklist, asset_dir):
    assert _get_presets(client, admin_token) == []
