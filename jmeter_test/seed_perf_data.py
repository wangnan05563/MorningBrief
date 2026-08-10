"""20_News 性能测试数据灌入脚本。

目标：在 data/news.db 中灌入真实量级测试数据，使读/写接口查询非平凡：
- channels >= 30（现有 10 + 新增 20）
- episodes >= 1000（现有 ~112 + 新增 ~900），其中含 date=今日 且 status=published 的行（/today 依赖）
- comments >= 5000
- users >= 200（c 端测试用户之外新增性能用户）
- favorites / play_log / play_progress / channel_subscription / feedback 适量

设计要点：
- 纯 DB 写入，不触发任何外部服务（LLM/TTS/COS）。
- 所有新增 episode 的 status='published'，否则 /today、/history、/search 过滤不到。
- 复用现有 script.id（episodes.{id}/script 需要 script 存在）。
- episode_fts 由 INSERT 触发器自动同步，search 直接可用。
- 幂等：检测到已存在 jmeter_perf_ 前缀用户则跳过，避免重复灌入。
"""
import json
import random
import sqlite3
from datetime import date, datetime, timedelta

BACKEND_DIR = __file__.rsplit("\\", 2)[0] if "\\" in __file__ else __file__.rsplit("/", 2)[0]
# 兼容 jmeter_test/ 位于 backend 同级：DB 在 backend/data/news.db
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE.parent / "backend" / "data" / "news.db"
USER_INFO = HERE / "test_user_info.json"

KEYWORDS = ["科技", "财经", "体育", "国际", "健康", "文化", "教育", "汽车", "房产", "游戏", "AI", "新能源"]
TITLE_TPL = "性能测试节目 第{n}期 {kw}快讯"
CONTENTS = [
    "这是一条用于性能测试的评论内容，验证高并发写入路径。",
    "负载测试评论：系统在高并发下应保持稳定。",
    "压测样本评论，确认 SQLite 单写者串行化行为。",
    "性能基线评论数据，用于统计接口聚合。",
]


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] 数据库不存在: {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    try:
        # 幂等检查
        cur.execute("SELECT COUNT(*) FROM user WHERE openid LIKE 'jmeter_perf_%'")
        if cur.fetchone()[0] > 0:
            print("[INFO] 已检测到 jmeter_perf_ 前缀用户，跳过灌入（如需重灌请先清理）")
            return 0

        today = date.today()
        max_script = cur.execute("SELECT COALESCE(MAX(id),0) FROM script").fetchone()[0] or 1
        max_channel = cur.execute("SELECT COALESCE(MAX(id),0) FROM channel").fetchone()[0] or 10

        # 1) 新增频道至 30
        existing_channels = cur.execute("SELECT COUNT(*) FROM channel").fetchone()[0]
        new_channels = max(0, 30 - existing_channels)
        ch_rows = []
        for i in range(new_channels):
            cid = existing_channels + i + 1
            ch_rows.append((f"性能测试频道{cid:02d}", f"压测专用频道{cid}", 1, now_iso(), now_iso(), cid))
        if ch_rows:
            cur.executemany(
                "INSERT INTO channel (name, description, is_active, created_at, updated_at, display_order) "
                "VALUES (?,?,?,?,?,?)", ch_rows)
        total_channels = cur.execute("SELECT COUNT(*) FROM channel").fetchone()[0]
        print(f"[OK] 频道总数: {total_channels}")

        # 2) 新增用户至 >=200
        existing_users = cur.execute("SELECT COUNT(*) FROM user").fetchone()[0]
        new_users = max(0, 200 - existing_users)
        user_rows = []
        for i in range(new_users):
            user_rows.append((f"jmeter_perf_{i+1:04d}", f"压测用户{i+1}", 0, 0))
        if user_rows:
            cur.executemany(
                "INSERT INTO user (openid, nickname, total_listen_duration, total_listen_count) VALUES (?,?,?,?)",
                user_rows)
        perf_user_ids = [r[0] for r in cur.execute(
            "SELECT id FROM user WHERE openid LIKE 'jmeter_perf_%'").fetchall()]
        print(f"[OK] 用户总数: {cur.execute('SELECT COUNT(*) FROM user').fetchone()[0]} (新增 {new_users})")

        # 3) 新增 episodes 至 >=1000
        existing_eps = cur.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
        target_eps = max(1000, existing_eps)
        new_eps = target_eps - existing_eps
        ep_rows = []
        for i in range(new_eps):
            # 前 30 条设为今日（保证 /today 有数据），其余散布过去 30 天
            if i < total_channels:
                d = today
            else:
                d = today - timedelta(days=random.randint(0, 30))
            kw = random.choice(KEYWORDS)
            ep_rows.append((
                d.isoformat(),
                random.randint(1, total_channels),
                TITLE_TPL.format(n=existing_eps + i + 1, kw=kw),
                random.randint(180, 720),
                f"http://127.0.0.1:8000/audio/perf_{existing_eps+i+1}.mp3",
                None,
                random.randint(1, max_script) if max_script else None,
                '["%s"]' % kw,
                "published",
                0,
                None,
                None,
                f"{d.isoformat()} 08:00:00",
                now_iso(),
                now_iso(),
                None,
            ))
        cur.executemany(
            "INSERT INTO episode (date, channel_id, title, duration, audio_url, cover_url, "
            "script_id, categories, status, is_backup, workflow_id, review_id, published_at, "
            "created_at, updated_at, hls_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ep_rows)
        total_eps = cur.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
        print(f"[OK] 节目总数: {total_eps} (新增 {new_eps})")

        # 4) 新增 comments 至 >=5000
        existing_comments = cur.execute("SELECT COUNT(*) FROM comment").fetchone()[0]
        target_comments = max(5000, existing_comments)
        new_comments = target_comments - existing_comments
        # 选取部分 episode id 用于评论归属
        ep_ids = [r[0] for r in cur.execute("SELECT id FROM episode ORDER BY id DESC LIMIT 1000").fetchall()]
        comment_rows = []
        for i in range(new_comments):
            uid = random.choice(perf_user_ids)
            epid = random.choice(ep_ids)
            comment_rows.append((
                str(uid), f"压测用户{uid}", None, epid,
                random.choice(CONTENTS), random.randint(0, 50), now_iso()))
        cur.executemany(
            "INSERT INTO comment (user_id, user_name, user_avatar, episode_id, content, like_count, created_at) "
            "VALUES (?,?,?,?,?,?,?)", comment_rows)
        print(f"[OK] 评论总数: {cur.execute('SELECT COUNT(*) FROM comment').fetchone()[0]} (新增 {new_comments})")

        # 5) 读取测试用户 id（来自 setup.py），为其预置 favorites / play_log / play_progress / channel_subscription
        test_user_id = None
        if USER_INFO.exists():
            info = json.loads(USER_INFO.read_text(encoding="utf-8"))
            test_user_id = info.get("user_id")
        print(f"[INFO] 测试用户 id={test_user_id}")

        def sample_eps(n):
            return random.sample(ep_ids, min(n, len(ep_ids)))

        fav_rows = []
        plog_rows = []
        pprog_rows = []
        csub_rows = []
        # 测试用户
        if test_user_id:
            for epid in sample_eps(50):
                fav_rows.append((str(test_user_id), epid, now_iso()))
            for epid in sample_eps(80):
                plog_rows.append((test_user_id, epid, random.randint(0, 600), 600,
                                   random.choice([0, 1]), now_iso()))
            for epid in sample_eps(80):
                pprog_rows.append((test_user_id, epid, random.randint(0, 600), 600,
                                   random.choice([0, 1]), now_iso()))
            for chid in random.sample(range(1, total_channels + 1), min(20, total_channels)):
                csub_rows.append((test_user_id, chid, now_iso()))
        # 性能用户
        for uid in perf_user_ids[:150]:
            for epid in sample_eps(10):
                fav_rows.append((str(uid), epid, now_iso()))
            for epid in sample_eps(15):
                plog_rows.append((uid, epid, random.randint(0, 600), 600,
                                  random.choice([0, 1]), now_iso()))
            for epid in sample_eps(15):
                pprog_rows.append((uid, epid, random.randint(0, 600), 600,
                                   random.choice([0, 1]), now_iso()))
            for chid in random.sample(range(1, total_channels + 1), min(8, total_channels)):
                csub_rows.append((uid, chid, now_iso()))
        if fav_rows:
            cur.executemany("INSERT INTO favorite (user_id, episode_id, created_at) VALUES (?,?,?)", fav_rows)
        if plog_rows:
            cur.executemany(
                "INSERT INTO play_log (user_id, episode_id, position, duration, completed, played_at) "
                "VALUES (?,?,?,?,?,?)", plog_rows)
        if pprog_rows:
            cur.executemany(
                "INSERT INTO play_progress (user_id, episode_id, position, duration, completed, updated_at) "
                "VALUES (?,?,?,?,?,?)", pprog_rows)
        if csub_rows:
            cur.executemany(
                "INSERT INTO channel_subscription (user_id, channel_id, created_at) VALUES (?,?,?)", csub_rows)

        # 6) 反馈适量
        fb_categories = ["bug", "suggestion", "praise", "other"]
        fb_rows = [(f"perf{i:05d}", str(random.choice(perf_user_ids)), random.choice(fb_categories),
                    "性能测试反馈内容用于验证写入路径的稳定性与吞吐。", None, "pending", now_iso(), now_iso())
                   for i in range(300)]
        cur.executemany(
            "INSERT INTO feedback (id, user_id, category, content, contact, status, created_at, synced_at) "
            "VALUES (?,?,?,?,?,?,?,?)", fb_rows)

        conn.commit()
        print("[OK] favorites/play_log/play_progress/channel_subscription/feedback 已写入")
        print(f"[DONE] 灌入完成。episode={total_eps}, comment={cur.execute('SELECT COUNT(*) FROM comment').fetchone()[0]}, "
              f"user={cur.execute('SELECT COUNT(*) FROM user').fetchone()[0]}, "
              f"favorite={cur.execute('SELECT COUNT(*) FROM favorite').fetchone()[0]}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
