# -*- coding: utf-8 -*-
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.core.security import hash_password
import sqlite3


def seed(db_path, username='admin', password='admin123', role='admin', nickname='Admin'):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS admin_user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'operator',
        nickname TEXT,
        status INTEGER NOT NULL DEFAULT 1,
        last_login_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK (role IN ('admin', 'operator')),
        CHECK (status IN (0, 1))
    )''')
    conn.commit()
    cur.execute('SELECT COUNT(*) FROM admin_user WHERE username = ?', (username,))
    count = cur.fetchone()[0]
    if count > 0:
        print('  [seed] Admin user already exists, skipping.')
        conn.close()
        return False
    pwd_hash = hash_password(password)
    cur.execute(
        'INSERT INTO admin_user (username, password_hash, role, status, nickname) VALUES (?, ?, ?, 1, ?)',
        (username, pwd_hash, role, nickname),
    )
    conn.commit()
    conn.close()
    print(f'  [seed] Created admin user: {username}/{password}')
    return True


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # 与运行时路径解析保持一致：dev 模式 → backend/data/news.db，exe 模式 → exe 同级 data/news.db
        # 之前默认指向 dist/MorningBrief/data/news.db，与开发态运行时数据库不一致，导致 dev 模式登录失败
        from app.paths import resolve_db_path
        db_path = str(resolve_db_path())
    if not Path(db_path).exists():
        print(f'  [seed] Database not found at {db_path}, creating...')
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    seed(db_path)


if __name__ == '__main__':
    main()
