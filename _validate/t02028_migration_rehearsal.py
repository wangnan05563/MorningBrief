"""T02028 库结构变更预演：在 news.db 的副本上跑迁移，验证幂等与存量数据安全。

硬约束来源：任务正文要求「涉及库结构变更先在复制库验证迁移，再上真实库，并留备份」。
本脚本只碰副本，不碰 backend/data/news.db。
"""
import asyncio
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

SRC = BACKEND / "data" / "news.db"
COPY = Path(__file__).with_name("t02028_dbcopy.db")

SNAPSHOT_TABLES = ("review", "episode")


def snapshot(conn):
    """抓取迁移前的表结构与全部行数据指纹，用于迁移后逐字节比对。"""
    out = {}
    for t in SNAPSHOT_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        rows = [tuple(r) for r in conn.execute(f"SELECT * FROM {t}")]
        out[t] = (cols, rows)
    return out


def main():
    import shutil
    shutil.copyfile(SRC, COPY)
    before = snapshot(sqlite3.connect(str(COPY)))
    for t, (cols, rows) in before.items():
        print(f"[copy] {t}: {len(cols)} 列 / {len(rows)} 行")

    from app import paths
    paths.resolve_db_path = lambda *a, **k: str(COPY)
    import app.main as m
    # 重绑函数内 import 的引用（函数里是 from app.paths import resolve_db_path）
    for run in (1, 2, 3):
        asyncio.run(m._migrate_duration_trace_columns())
        conn = sqlite3.connect(str(COPY))
        after = snapshot(conn)
        for t in SNAPSHOT_TABLES:
            old_cols, old_rows = before[t]
            new_cols, new_rows = after[t]
            added = [c for c in new_cols if c not in old_cols]
            assert new_rows == [
                r + (None,) * len(added)
                for r in old_rows
            ], f"{t} 存量行在迁移后发生变化"
            if run == 1:
                print(f"[run {run}] {t} 新增列: {added}")
            else:
                print(f"[run {run}] {t} 列集不变: {added == []}, 行数 {len(new_rows)}")
            before[t] = ([c for c in new_cols], old_rows)
        conn.close()
    print("[ok] 三次运行幂等，存量行仅右补 NULL，无改写/丢失")


if __name__ == "__main__":
    main()
