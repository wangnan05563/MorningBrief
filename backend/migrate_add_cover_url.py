"""SQLite 表结构迁移：为 material 表增加 cover_url 列。

SQLite 的 ALTER TABLE ADD COLUMN 不会破坏现有数据，且 SQLAlchemy create_all
不会修改已存在的表结构，因此通过显式迁移脚本补列。

幂等：列已存在时 PRAGMA table_info 会检测到，跳过 ALTER。
"""
import logging
import sqlite3
import sys
from pathlib import Path

# 允许脚本独立运行：把 backend 目录加入 sys.path，复用 app.paths 解析默认 DB 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.paths import resolve_db_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        logger.warning("数据库文件不存在，跳过迁移: %s", db_path)
        return

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(material)")
        cols = [row[1] for row in cur.fetchall()]
        if "cover_url" in cols:
            logger.info("material.cover_url 列已存在，跳过 ALTER")
            return
        # SQLite ADD COLUMN 不支持 IF NOT EXISTS，需先 PRAGMA 检测
        cur.execute("ALTER TABLE material ADD COLUMN cover_url VARCHAR(512)")
        conn.commit()
        logger.info("迁移成功：material 表新增 cover_url 列")
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = resolve_db_path()
    logger.info("目标数据库: %s", db_path)
    migrate(db_path)
