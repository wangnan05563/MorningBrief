# -*- coding: utf-8 -*-
"""频道种子数据初始化脚本。

参考 seed_admin.py 的设计：幂等执行，已存在的频道自动跳过。
默认内置 8 个常用新闻频道分类，覆盖主流播客新闻场景。

用法：
    python seed_channels.py [db_path]

不指定 db_path 时，按优先级回退：
    1. 命令行参数
    2. 项目根目录 dist/20-news/data/news.db（打包后路径）
    3. backend/data/news.db（开发态路径）
"""
import sqlite3
import sys
from pathlib import Path

# 默认频道列表：覆盖播客新闻常见分类，按通用性与受众广度排序
# name 唯一，description 简明描述频道定位（≤256 字符，符合模型约束）
DEFAULT_CHANNELS = [
    ("科技前沿", "科技创新、人工智能、互联网行业动态与产品评测"),
    ("财经观察", "股市行情、宏观经济、金融政策与商业分析"),
    ("体育速递", "国内外体育赛事、运动员风采与赛场解读"),
    ("娱乐焦点", "影视、音乐、明星动态与文娱产业资讯"),
    ("国际视野", "国际时事、全球要闻与地缘政治深度解读"),
    ("社会民生", "社会热点、民生政策与公共事件追踪"),
    ("健康养生", "医疗健康、疾病预防与生活方式科普"),
    ("教育资讯", "教育政策、学习方法与升学留学指南"),
]


def seed(db_path: str, channels=None) -> int:
    """向 channel 表插入种子数据。返回实际新增的频道数量。

    幂等设计：按 name 唯一约束判断，已存在的频道跳过，不重复插入。
    表结构由 ORM 模型在应用启动时自动创建，此处仅做数据填充。
    """
    if channels is None:
        channels = DEFAULT_CHANNELS

    db_file = Path(db_path)
    if not db_file.exists():
        # 数据库不存在时仅提示，不自动建表（避免 schema 不一致）
        # 应用首次启动会通过 Base.metadata.create_all 建表
        print(f"  [seed] 数据库不存在: {db_path}，请先启动一次应用以初始化表结构")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 检查 channel 表是否存在（避免应用未启动时误操作）
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel'")
    if cur.fetchone() is None:
        print("  [seed] channel 表不存在，请先启动一次应用以初始化表结构")
        conn.close()
        return 0

    inserted = 0
    skipped = 0
    for name, description in channels:
        # 幂等检查：按 name 判断是否已存在
        cur.execute("SELECT COUNT(*) FROM channel WHERE name = ?", (name,))
        if cur.fetchone()[0] > 0:
            skipped += 1
            continue
        cur.execute(
            "INSERT INTO channel (name, description, is_active) VALUES (?, ?, 1)",
            (name, description),
        )
        inserted += 1
        print(f"  [seed] 新增频道: {name}")

    conn.commit()
    conn.close()
    print(f"  [seed] 完成：新增 {inserted} 个，跳过 {skipped} 个已存在频道")
    return inserted


def resolve_db_path() -> str:
    """解析数据库路径，支持命令行参数与默认回退策略。"""
    if len(sys.argv) > 1:
        return sys.argv[1]

    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    # 回退顺序：打包后路径 → 开发态路径
    dist_db = project_root / "dist" / "20-news" / "data" / "news.db"
    if dist_db.exists():
        return str(dist_db)
    return str(backend_dir / "data" / "news.db")


def main():
    db_path = resolve_db_path()
    print(f"  [seed] 数据库路径: {db_path}")
    seed(db_path)


if __name__ == "__main__":
    main()
