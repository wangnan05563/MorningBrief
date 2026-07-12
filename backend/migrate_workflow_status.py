"""迁移脚本：删除 workflow 表的 ck_workflow_status 约束。

背景：V1.2 队列管理新增 WorkflowStatus.queued 状态，但存量数据库的 CHECK 约束
仍为 ('running', 'success', 'failed', 'cancelled')，导致插入 'queued' 时
触发 IntegrityError。

SQLite 不支持 ALTER TABLE DROP CONSTRAINT，需用"重建表"方式：
1. 创建新表（无 ck_workflow_status 约束）
2. 复制数据
3. 删除旧表
4. 重命名新表
5. 重建索引

幂等性：若 ck_workflow_status 约束已不存在则跳过。
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "news.db"


def needs_migration(conn: sqlite3.Connection) -> bool:
    """检查是否需要迁移（ck_workflow_status 约束是否存在）。"""
    cursor = conn.execute("SELECT sql FROM sqlite_master WHERE name='workflow'")
    row = cursor.fetchone()
    if not row:
        print("workflow 表不存在，跳过迁移")
        return False
    return "ck_workflow_status" in row[0]


def migrate(conn: sqlite3.Connection) -> None:
    """执行重建表迁移。"""
    conn.executescript("""
        -- 1. 创建新表（无 ck_workflow_status 约束，与 ORM 模型一致）
        CREATE TABLE workflow_new (
            id VARCHAR(64) NOT NULL,
            episode_date DATE NOT NULL,
            source VARCHAR(16) NOT NULL,
            status VARCHAR(16),
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            finished_at DATETIME,
            error TEXT,
            channel_id INTEGER REFERENCES channel(id) ON DELETE SET NULL,
            priority INTEGER DEFAULT 5,
            PRIMARY KEY (id),
            CONSTRAINT ck_workflow_source CHECK (source IN ('cron', 'manual'))
        );

        -- 2. 复制数据
        INSERT INTO workflow_new (id, episode_date, source, status, started_at, finished_at, error, channel_id, priority)
        SELECT id, episode_date, source, status, started_at, finished_at, error, channel_id, priority
        FROM workflow;

        -- 3. 删除旧表
        DROP TABLE workflow;

        -- 4. 重命名新表
        ALTER TABLE workflow_new RENAME TO workflow;

        -- 5. 重建索引（DROP TABLE 会一并删除索引）
        CREATE INDEX IF NOT EXISTS idx_date ON workflow (episode_date);
        CREATE INDEX IF NOT EXISTS idx_status ON workflow (status);
        CREATE INDEX IF NOT EXISTS idx_workflow_channel ON workflow (channel_id);
        CREATE INDEX IF NOT EXISTS idx_workflow_priority ON workflow (priority);
    """)
    conn.commit()


def main() -> int:
    if not DB_PATH.exists():
        print(f"数据库文件不存在: {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    try:
        if not needs_migration(conn):
            print("ck_workflow_status 约束不存在，无需迁移")
            return 0

        print("检测到 ck_workflow_status 约束，开始迁移...")
        migrate(conn)
        print("迁移完成：已删除 ck_workflow_status 约束，workflow 表现在支持 queued 状态")

        # 验证
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE name='workflow'")
        new_sql = cursor.fetchone()[0]
        assert "ck_workflow_status" not in new_sql, "迁移后仍存在 ck_workflow_status 约束"
        print("验证通过：ck_workflow_status 约束已删除")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
