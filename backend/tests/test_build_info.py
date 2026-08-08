"""build_info.py 生成器测试。

验证生成器能写出可被 import 的 _build_info.py，且字段类型正确、
版本号优先级（VERSION 文件 > git tag > 兜底）生效。
"""
import importlib
import os
import sys
import textwrap

import pytest

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_generated(target_path: str) -> dict:
    """把生成的 _build_info.py 当作临时模块导入，返回其字段。"""
    spec = importlib.util.spec_from_file_location("_build_info_gen_test", target_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {
        "version": getattr(mod, "__version__", None),
        "build_date": getattr(mod, "build_date", None),
        "git_sha": getattr(mod, "git_sha", None),
    }


def _import_build_info():
    """按绝对路径加载 backend/build_info.py（backend 非包，避免 import backend 失败）。"""
    spec = importlib.util.spec_from_file_location(
        "_build_info_module", os.path.join(_BACKEND_DIR, "build_info.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generate_writes_importable_module(tmp_path, monkeypatch):
    """生成器写出可被 import 的模块，三个字段均为字符串。"""
    bi = _import_build_info()

    # 把目标重定向到临时目录，避免污染真实 app/_build_info.py
    target = tmp_path / "app" / "_build_info.py"
    monkeypatch.setattr(bi, "_TARGET", str(target))
    # 无 VERSION 文件、且 git 调用被 mock 返回 tag，验证 version 取自 tag
    monkeypatch.setattr(bi, "_read_version_file", lambda: None)
    monkeypatch.setattr(
        bi, "_git",
        lambda *a: "v9.9.9" if a and a[0] == "describe" else "abc1234",
    )

    fields = bi.generate()

    assert target.exists()
    data = _load_generated(str(target))
    assert data["version"] == "9.9.9"  # tag 前缀 v 被去掉
    assert data["git_sha"] == "abc1234"
    assert isinstance(data["build_date"], str)
    assert len(data["build_date"].split("-")) == 3  # YYYY-MM-DD
    # 返回字段与写入内容一致
    assert fields["version"] == data["version"]


def test_version_file_takes_precedence(tmp_path, monkeypatch):
    """VERSION 文件优先于 git tag。"""
    bi = _import_build_info()

    target = tmp_path / "app" / "_build_info.py"
    version_file = tmp_path / "VERSION"
    version_file.write_text("2.3.4\n", encoding="utf-8")
    monkeypatch.setattr(bi, "_TARGET", str(target))
    monkeypatch.setattr(bi, "_VERSION_FILE", str(version_file))
    # tag 返回不同值，验证未被采用
    monkeypatch.setattr(bi, "_git", lambda *a: "v1.0.0" if a and a[0] == "describe" else "xys7890")

    fields = bi.generate()
    assert fields["version"] == "2.3.4"


def test_fallback_version_when_no_source(tmp_path, monkeypatch):
    """无 VERSION 文件且 git 不可用时兜底 1.0.0，sha 为 unknown。"""
    bi = _import_build_info()

    target = tmp_path / "app" / "_build_info.py"
    monkeypatch.setattr(bi, "_TARGET", str(target))
    monkeypatch.setattr(bi, "_VERSION_FILE", str(tmp_path / "NOPE_VERSION"))
    monkeypatch.setattr(bi, "_git", lambda *a: None)

    fields = bi.generate()
    assert fields["version"] == "1.0.0"
    assert fields["git_sha"] == "unknown"
