"""M1 Phase 2 单元测试：选题策略 + 频道迁移。

运行时：backend/.venv/Scripts/python.exe temp/test_strategy_unit.py
仅依赖项目 venv，不启 HTTP 服务；测试库走临时文件，结束即清理。
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime

import sqlite3

# 让 import app.* 可解析（cwd=backend）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workflow.llm.rewriter import (  # noqa: E402
    _select_top_materials,
    _parse_material_ids,
)
from app.paths import resolve_db_path as _real_resolve_db_path  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {extra}")


def mk(title, cat, auth, mid):
    return {
        "id": mid,
        "title": title,
        "category": cat,
        "source_authority": auth,
        "published_at": datetime(2026, 8, 11, 0, 0, 0),
    }


def test_parse_material_ids():
    print("== _parse_material_ids ==")
    check("None -> None", _parse_material_ids(None) is None)
    check("空串 -> None", _parse_material_ids("") is None)
    check("纯空白 -> None", _parse_material_ids("   ") is None)
    check("'[]' -> None", _parse_material_ids("[]") is None)
    check("'[1,2,3]' -> [1,2,3]", _parse_material_ids("[1,2,3]") == [1, 2, 3])
    check("含 null 被跳过", _parse_material_ids("[1,2,null,3]") == [1, 2, 3])
    check("字符串数字被 int() 归一化", _parse_material_ids('[1,2,"3"]') == [1, 2, 3])
    check("单引号非 JSON -> None", _parse_material_ids("[1,2,'3']") is None)
    check("非法 JSON -> None", _parse_material_ids("1,2,3") is None)
    check("非数组 -> None", _parse_material_ids('{"a":1}') is None)


def test_select_top_materials():
    print("== _select_top_materials ==")
    mats = [
        mk("新闻", "A", 0.9, 1),
        mk("新闻", "A", 0.5, 2),
        mk("新闻", "B", 0.8, 3),
        mk("新闻", "B", 0.4, 4),
        mk("新闻", "C", 0.7, 5),
    ]
    # heat: 品类轮询第一轮取 A1/B1/C1（id 1,3,5）
    got = _select_top_materials(mats, top_n=3, strategy="heat")
    ids = [m["id"] for m in got]
    check("heat 第一轮覆盖品类顺序 [1,3,5]", ids == [1, 3, 5], f"got {ids}")
    check("heat 长度受 top_n 约束", len(got) <= 3)

    # heat: top_n 大于素材数不报错
    got_all = _select_top_materials(mats, top_n=99, strategy="heat")
    check("heat top_n 超量返回全部 5 条", len(got_all) == 5)

    # outline: 按 id 升序切片
    shuffled = [mats[2], mats[0], mats[1], mats[4], mats[3]]  # id 3,1,2,5,4
    got_o = _select_top_materials(shuffled, top_n=3, strategy="outline")
    ids_o = [m["id"] for m in got_o]
    check("outline 按 id 升序前 3 [1,2,3]", ids_o == [1, 2, 3], f"got {ids_o}")

    # manual: 按指定顺序，仅保留命中
    got_m = _select_top_materials(mats, top_n=3, strategy="manual", manual_ids=[4, 2, 9])
    ids_m = [m["id"] for m in got_m]
    check("manual 按指定顺序 [4,2]", ids_m == [4, 2], f"got {ids_m}")

    # manual: 空 manual_ids -> 空选
    got_mt = _select_top_materials(mats, top_n=3, strategy="manual", manual_ids=None)
    check("manual 空 ID -> 空选", got_mt == [])

    # 默认 strategy=heat
    got_d = _select_top_materials(mats, top_n=3)
    check("默认 strategy=heat", [m["id"] for m in got_d] == [1, 3, 5])


def test_channel_migration():
    print("== channel 表迁移（selection_strategy/enable_ad/manual_material_ids）==")
    tmp = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(tmp)
    # 模拟“旧 schema”：含既有列，但不含本期三列
    conn.execute(
        "CREATE TABLE channel ("
        "id INTEGER PRIMARY KEY, name TEXT, display_order INTEGER NOT NULL DEFAULT 0,"
        "material_lookback_days INTEGER)"
    )
    conn.commit()
    conn.close()

    # monkeypatch resolve_db_path -> 临时库
    import app.paths as paths_mod
    paths_mod.resolve_db_path = lambda: __import__("pathlib").Path(tmp)

    from app.main import _migrate_channel_schema
    asyncio.run(_migrate_channel_schema())

    conn = sqlite3.connect(tmp)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(channel)").fetchall()}
    conn.close()
    for c in ("selection_strategy", "enable_ad", "manual_material_ids"):
        check(f"迁移后存在列 {c}", c in cols)

    # 幂等：再跑一次不应报错，列仍在
    asyncio.run(_migrate_channel_schema())
    conn = sqlite3.connect(tmp)
    cols2 = {r[1] for r in conn.execute("PRAGMA table_info(channel)").fetchall()}
    conn.close()
    check("幂等：二次迁移列仍在", {"selection_strategy", "enable_ad", "manual_material_ids"} <= cols2)

    # 可写入/读出
    conn = sqlite3.connect(tmp)
    conn.execute(
        "INSERT INTO channel (name, selection_strategy, enable_ad, manual_material_ids)"
        " VALUES (?,?,?,?)",
        ("课程频道", "manual", 0, "[10,20]"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT selection_strategy, enable_ad, manual_material_ids FROM channel WHERE name=?",
        ("课程频道",),
    ).fetchone()
    conn.close()
    check("可写入并读回三列", row == ("manual", 0, "[10,20]"), f"got {row}")

    # 还原 monkeypatch 并清理
    paths_mod.resolve_db_path = _real_resolve_db_path
    try:
        os.remove(tmp)
    except OSError:
        pass


if __name__ == "__main__":
    test_parse_material_ids()
    test_select_top_materials()
    test_channel_migration()
    print(f"\n==== 结果: {PASS} 通过 / {FAIL} 失败 ====")
    sys.exit(1 if FAIL else 0)
