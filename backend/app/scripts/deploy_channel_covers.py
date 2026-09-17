"""把已生成的频道 AI 封面部署到目标实例数据目录（T00731 补充）。

背景：AI 封面生成在开发库（backend/data/channel_assets + news.db cover_url），
而用户小程序连接的是**另一个后端实例**（独立数据目录）。本脚本把封面文件复制到
目标实例的 channel_assets 目录，并在其实例库中把各频道 `cover_url` 指向对应文件。

用法（backend 目录）：
    python -m app.scripts.deploy_channel_covers --data-dir "<实例数据目录>"

<data-dir> 是实例的 data 目录（内含 news.db），例如打包安装后的
`<安装目录>\\data` 或自建实例的 backend/data。脚本幂等，可重复执行。
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "data" / "channel_assets"


def main() -> int:
    parser = argparse.ArgumentParser(description="部署频道 AI 封面到目标实例（T00731）")
    parser.add_argument("--data-dir", required=True, help="目标实例的 data 目录（内含 news.db）")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    db_path = data_dir / "news.db"
    if not db_path.exists():
        print(f"[error] 未找到实例库：{db_path}")
        return 2
    if not SRC_DIR.exists() or not list(SRC_DIR.glob("channel_*.jpg")):
        print(f"[error] 源目录无封面文件：{SRC_DIR}")
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
        for src in sorted(SRC_DIR.glob("channel_*.jpg")):
            dst = dest_dir / src.name
            if src.resolve() == dst.resolve():
                skipped += 1  # 源即目标（同目录部署），无需复制
                continue
            shutil.copyfile(src, dst)
            copied += 1
            ch_id = src.stem.split("_")[-1]
            row = conn.execute(
                "SELECT cover_url FROM channel WHERE id = ?", (ch_id,)
            ).fetchone()
            if row is None:
                skipped += 1
                continue
            cur_cover = row[0] or ""
            if cur_cover.startswith("/channel-assets/"):
                conn.execute(
                    "UPDATE channel SET cover_url = ? WHERE id = ?",
                    (f"/channel-assets/{src.name}", ch_id),
                )
                assigned += 1
            elif not cur_cover:
                conn.execute(
                    "UPDATE channel SET cover_url = ? WHERE id = ?",
                    (f"/channel-assets/{src.name}", ch_id),
                )
                assigned += 1
            else:
                skipped += 1  # 已有人工配置的封面，不覆盖
        conn.commit()

        print(f"[done] 复制封面 {copied} 张；设为频道封面 {assigned} 个；跳过 {skipped} 个"
              f"（已有 /channel-assets 封面或频道不存在）")
        print("[hint] 重启目标实例的后端服务后，今日节目接口将下发 channel_cover 字段，"
              "小程序首页卡片即显示 AI 封面（需实例代码包含 T00724/T00731 的载荷改动）。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
