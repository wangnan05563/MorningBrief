# -*- coding: utf-8 -*-
"""课程(course)频道种子数据初始化脚本。

幂等执行：按 name 唯一约束判断，已存在的频道自动跳过，不重复插入。
参考 seed_channels.py 的设计，但针对 course 类型频道，默认配置：
  - channel_type='course'     驱动小程序课程皮肤 / 章节列表 UI
  - selection_strategy='outline'  按文档章节顺序选题（课程稿连贯性）
  - enable_ad=0               课程 / 资料频道零广告
  - disclaimer_level='strong' AI 生成课程须显式风险提示
  - type_label='课程'          冗余中文标签，避免前端硬编码

用法：
    python seed_course_channel.py [db_path]

不指定 db_path 时，使用 app.paths.resolve_db_path() 统一解析路径，
确保 dev / exe 模式下路径一致。
"""
import sqlite3
import sys
from pathlib import Path

# 默认课程频道列表：(name, description)
# 此处内置一个示例课程频道，可按业务需要继续扩展。
DEFAULT_COURSE_CHANNELS = [
    ("AI 通识课堂", "面向大众的 AI 通识语音课程：从基础概念到实际应用，体系化讲解人工智能核心知识。"),
]


def seed(db_path: str, channels=None) -> int:
    """向 channel 表插入课程频道种子数据。返回实际新增的频道数量。

    幂等设计：按 name 唯一约束判断，已存在的频道跳过，不重复插入。
    """
    if channels is None:
        channels = DEFAULT_COURSE_CHANNELS

    db_file = Path(db_path)
    if not db_file.exists():
        print(f"  [seed-course] 数据库不存在: {db_path}，请先启动一次应用以初始化表结构")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel'")
    if cur.fetchone() is None:
        print("  [seed-course] channel 表不存在，请先启动一次应用以初始化表结构")
        conn.close()
        return 0

    inserted = 0
    skipped = 0
    for name, description in channels:
        cur.execute("SELECT COUNT(*) FROM channel WHERE name = ?", (name,))
        if cur.fetchone()[0] > 0:
            skipped += 1
            print(f"  [seed-course] 跳过已存在频道: {name}")
            continue
        cur.execute(
            """INSERT INTO channel
               (name, description, is_active, channel_type, selection_strategy,
                enable_ad, disclaimer_level, type_label, display_order)
               VALUES (?, ?, 1, 'course', 'outline', 0, 'strong', '课程', 0)""",
            (name, description),
        )
        inserted += 1
        print(f"  [seed-course] 新增课程频道: {name}")

    conn.commit()
    conn.close()
    print(f"  [seed-course] 完成：新增 {inserted} 个，跳过 {skipped} 个已存在频道")
    return inserted


def _resolve_db_path() -> str:
    """解析数据库路径：命令行参数优先，否则使用 app.paths.resolve_db_path()。"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        from app.paths import resolve_db_path
        return str(resolve_db_path())
    except Exception:
        backend_dir = Path(__file__).resolve().parent
        return str(backend_dir / "data" / "news.db")


def main():
    db_path = _resolve_db_path()
    print(f"  [seed-course] 数据库路径: {db_path}")
    seed(db_path)


if __name__ == "__main__":
    main()
