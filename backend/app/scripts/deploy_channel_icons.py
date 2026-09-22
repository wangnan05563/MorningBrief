"""把已生成的频道图标（channel_{id}_icon.png）部署到目标实例数据目录（T00731 遗留）。

背景：图标生成在开发库（backend/data/channel_assets + news.db icon_url），而用户连接的是
独立数据目录的实例。本脚本把 icon 复制到目标实例 channel_assets，并在其实例库中把各频道
icon_url 指向对应文件（仅当当前为空，不覆盖人工配置）。脚本幂等，可重复执行。

用法（backend 目录）：
    python -m app.scripts.deploy_channel_icons --data-dir "<实例数据目录>"
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "data" / "channel_assets"


def main() -> int:
    parser = argparse.ArgumentParser(description="部署频道 AI 图标到目标实例（T00731 遗留）")
    parser.add_argument("--data-dir", required=True, help="目标实例的 data 目录（内含 news.db）")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    db_path = data_dir / "news.db"
    if not db_path.exists():
        print(f"[error] 未找到实例库：{db_path}")
        return 2
    if not SRC_DIR.exists() or not list(SRC_DIR.glob("channel_*_icon.png")):
        print(f"[error] 源目录无图标文件：{SRC_DIR}")
        return 2

    dest_dir = data_dir / "channel_assets"
    dest_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(channel)")}
        if "icon_url" not in cols:
            conn.execute("ALTER TABLE channel ADD COLUMN icon_url TEXT")
            print("[ok] channel 表已补 icon_url 列")

        copied = assigned = skipped = 0
        for src in sorted(SRC_DIR.glob("channel_*_icon.png")):
            dst = dest_dir / src.name
            if src.resolve() == dst.resolve():
                skipped += 1
                continue
            shutil.copyfile(src, dst)
            copied += 1
            ch_id = src.stem.split("_")[1]  # channel_1_icon -> 1
            row = conn.execute(
                "SELECT icon_url FROM channel WHERE id = ?", (ch_id,)
            ).fetchone()
            if row is None:
                skipped += 1
                continue
            cur = row[0] or ""
            # 仅当当前无 icon 或已是指向 channel-assets 时才设（不覆盖人工配置）
            if not cur or cur.startswith("/channel-assets/"):
                conn.execute(
                    "UPDATE channel SET icon_url = ? WHERE id = ?",
                    (f"/channel-assets/{src.name}", ch_id),
                )
                assigned += 1
            else:
                skipped += 1
        conn.commit()

        print(f"[done] 复制图标 {copied} 张；设为频道图标 {assigned} 个；跳过 {skipped} 个")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())