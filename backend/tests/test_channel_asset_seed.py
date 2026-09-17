# -*- coding: utf-8 -*-
"""频道预制资产播种逻辑测试（T00731 打包补全）。

覆盖 seed_channel_assets_from 的语义：
- 缺失文件补齐、已存在文件不覆盖（用户替换过的同名资产必须保留）
- 非图片文件（.gitignore / .txt 等）与子目录（.backup-*）不被复制
- 源/目标同路径（开发态）短路返回 0
- 源目录不存在时安全返回 0（不抛异常，不阻断启动）
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import seed_channel_assets_from  # noqa: E402


def _write(path: Path, content: bytes = b"img") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_copies_missing_assets(tmp_path):
    """源目录资产应被补齐到目标目录。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "channel_1.jpg")
    _write(src / "channel_2.jpg")
    _write(src / "channel_3.png")

    copied = seed_channel_assets_from(src, dst)

    assert copied == 3
    assert sorted(p.name for p in dst.iterdir()) == ["channel_1.jpg", "channel_2.jpg", "channel_3.png"]


def test_does_not_overwrite_existing(tmp_path):
    """目标已存在的同名文件必须保留原内容（用户可能替换过封面）。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "channel_1.jpg", b"new")
    _write(src / "channel_2.jpg", b"new")
    _write(dst / "channel_1.jpg", b"user-customized")

    copied = seed_channel_assets_from(src, dst)

    assert copied == 1  # 仅 channel_2 被补齐
    assert (dst / "channel_1.jpg").read_bytes() == b"user-customized"
    assert (dst / "channel_2.jpg").read_bytes() == b"new"


def test_ignores_non_images_and_dirs(tmp_path):
    """非图片文件与子目录（如 .backup-* 备份目录）不参与播种。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "channel_1.jpg")
    _write(src / ".gitignore", b".backup-*/\n")
    _write(src / "readme.txt", b"x")
    _write(src / ".backup-20260918" / "channel_1.jpg", b"old")

    copied = seed_channel_assets_from(src, dst)

    assert copied == 1
    assert [p.name for p in dst.iterdir()] == ["channel_1.jpg"]


def test_same_dir_short_circuits(tmp_path):
    """开发态源即目标：直接返回 0，不做拷贝（也避免自我覆盖）。"""
    same = tmp_path / "assets"
    _write(same / "channel_1.jpg")

    assert seed_channel_assets_from(same, same) == 0


def test_missing_source_dir_returns_zero(tmp_path):
    """源目录不存在（未打包该资产）时安全返回 0，不抛异常。"""
    assert seed_channel_assets_from(tmp_path / "nope", tmp_path / "dst") == 0


def test_creates_destination_dir(tmp_path):
    """目标目录不存在时应自动创建。"""
    src = tmp_path / "src"
    dst = tmp_path / "deep" / "nested" / "channel_assets"
    _write(src / "channel_9.jpg")

    assert seed_channel_assets_from(src, dst) == 1
    assert (dst / "channel_9.jpg").exists()


def test_idempotent_second_run(tmp_path):
    """重复执行幂等：第二次不再拷贝。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "channel_1.jpg")

    assert seed_channel_assets_from(src, dst) == 1
    assert seed_channel_assets_from(src, dst) == 0


@pytest.mark.parametrize("name,copied", [
    ("channel_1.JPG", 1),   # 大写在白名单内（后缀大小写不敏感）
    ("channel_1.webp", 1),
    ("channel_1.jpeg", 1),
    ("channel_1.gif", 0),   # gif 不在白名单
    ("channel_1.mp3", 0),
])
def test_suffix_whitelist(tmp_path, name, copied):
    """后缀白名单与上传接口口径一致（jpg/jpeg/png/webp），大小写不敏感。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / name)

    assert seed_channel_assets_from(src, dst) == copied
