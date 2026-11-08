"""在沙箱库中创建压测账号、签发 token，并生成夹具与全量接口用例。

输出（均在 runtime/，含明文 token，已被 .gitignore 排除，勿提交）：
- tokens.json：C 端 / B 端 / 内部接口凭据
- fixtures.json：真实主键与查询参数取值
- cases.json：243 条 METHOD+path 用例（路径已填夹具）及覆盖类型
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SANDBOX_BACKEND = HERE / "sandbox" / "backend"
# 与 app/paths.py 一致：库固定在代码副本的 backend/data 下
DB = SANDBOX_BACKEND / "data" / "news.db"
RUNTIME = HERE / "runtime"
INVENTORY = HERE / "inventory.json"
PERF = json.loads((HERE / "perf_config.json").read_text(encoding="utf-8"))

os.environ["APP_ROLE"] = "api"
os.environ["SQLITE_DB_PATH"] = str(DB)
# 与 sandbox.py 同一套测试期覆盖：否则签出的管理端 token 仍是生产默认 2h，
# 4h soak 后段会整批 401（测试装置问题，不是服务缺陷）
for _k, _v in (PERF["sandbox"].get("env_overrides") or {}).items():
    os.environ[str(_k)] = str(_v)
sys.path.insert(0, str(SANDBOX_BACKEND))

C_OPENID = "perf_user_001"
ADMIN_USERNAME = "perf_admin"
SENTINEL_ADMIN_PASSWORD = PERF["secrets"]["admin_password_sentinel"]


def get_or_create_user(conn: sqlite3.Connection) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO user (openid, nickname, total_listen_duration, total_listen_count) "
        "VALUES (?, ?, 0, 0)",
        (C_OPENID, "性能测试用户"),
    )
    conn.commit()
    return conn.execute("SELECT id FROM user WHERE openid = ?", (C_OPENID,)).fetchone()[0]


def get_or_create_admin(conn: sqlite3.Connection) -> tuple[int, str]:
    from app.core.security import hash_password

    row = conn.execute("SELECT id FROM admin_user WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
    password_file = RUNTIME / "admin_password.txt"
    if row:
        if password_file.exists():
            return row[0], password_file.read_text(encoding="utf-8").strip()
        password = "Perf#" + secrets.token_urlsafe(12)
        conn.execute(
            "UPDATE admin_user SET password_hash = ? WHERE id = ?",
            (hash_password(password), row[0]),
        )
        conn.commit()
        password_file.write_text(password, encoding="utf-8")
        return row[0], password
    password = "Perf#" + secrets.token_urlsafe(12)
    conn.execute(
        "INSERT INTO admin_user (username, password_hash, role, nickname, status) VALUES (?, ?, 'admin', ?, 1)",
        (ADMIN_USERNAME, hash_password(password), "性能测试管理员"),
    )
    conn.commit()
    (RUNTIME / "admin_password.txt").write_text(password, encoding="utf-8")
    admin_id = conn.execute("SELECT id FROM admin_user WHERE username = ?", (ADMIN_USERNAME,)).fetchone()[0]
    return admin_id, password


def ensure_feedback(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute("SELECT id FROM feedback WHERE user_id = ? LIMIT 1", (str(user_id),)).fetchone()
    if row:
        return row[0]
    import uuid

    feedback_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO feedback (id, user_id, category, content, contact, status) VALUES (?, ?, 'other', '性能测试反馈', NULL, 'pending')",
        (feedback_id, str(user_id)),
    )
    conn.commit()
    return feedback_id


def pick(conn: sqlite3.Connection, sql: str, default=1):
    row = conn.execute(sql).fetchone()
    return row[0] if row else default


def build_fixtures(conn: sqlite3.Connection, user_id: int, admin_id: int, feedback_id: int) -> dict:
    today = date.today().isoformat()
    channel_id = pick(conn, "SELECT id FROM channel WHERE is_active = 1 ORDER BY id LIMIT 1")
    course_channel_id = pick(conn, "SELECT id FROM channel WHERE channel_type = 'course' AND is_active = 1 ORDER BY id LIMIT 1", channel_id)
    episode_id = pick(conn, "SELECT id FROM episode WHERE status = 'published' ORDER BY id DESC LIMIT 1")
    script_id = pick(conn, "SELECT id FROM script ORDER BY id DESC LIMIT 1")
    # 稿件查询按 workflow_id 过滤，没有稿件的 workflow 会 404（非缺陷）→ 取有稿件的那条
    workflow_id = pick(
        conn,
        "SELECT workflow_id FROM script WHERE workflow_id IS NOT NULL ORDER BY id DESC LIMIT 1",
        pick(conn, "SELECT id FROM workflow ORDER BY started_at DESC LIMIT 1", "wf-20260717-0002"),
    )
    material_id = pick(conn, "SELECT id FROM material ORDER BY id LIMIT 1")
    review_id = pick(conn, "SELECT id FROM review ORDER BY id DESC LIMIT 1")
    comment_id = pick(conn, "SELECT id FROM comment ORDER BY id LIMIT 1")
    notification_template_id = pick(conn, "SELECT id FROM notification_template ORDER BY id LIMIT 1")
    return {
        "channel_id": channel_id,
        "course_channel_id": course_channel_id,
        "episode_id": episode_id,
        "workflow_id": workflow_id,
        "script_id": script_id,
        "material_id": material_id,
        "review_id": review_id,
        "comment_id": comment_id,
        "user_id": user_id,
        "admin_id": admin_id,
        "feedback_id": feedback_id,
        "template_id": notification_template_id,
        # db-admin 只接受白名单表（见 db_admin_service.ALLOWED_TABLES），channel 不在其中
        "table": "episode",
        "pk_value": episode_id,
        "month": today[:7],
        "date": today,
        "keyword": "科技",
        "metric": "plays",
        "range": "7d",
        "url": f"http://{PERF['sandbox']['host']}:{PERF['sandbox']['port']}/api/health/live",
        "key": "perf/nonexistent.txt",
        "backup_key": "perf/backup-none.zip",
        "source_key": "perf/a.txt",
        "dest_key": "perf/b.txt",
        "filename": "perf.mp3",
        "path": "perf",
        "format": "csv",
        "limit": 10,
        "size": 10,
        "page": 1,
        "item_id": 999999,
        "stat_id": 999999,
        "task_id": "perf-none",
        "log_id": 999999,
        "placement_id": 999999,
        "missing_id": 999999,
    }


def _is_external(method: str, path: str) -> bool:
    """会出站（付费 LLM/TTS/COS/微信/Cloudflare/升级下载）的接口，不进压测流量。"""
    if path in ("/api/v1/auth/login", "/api/v1/cos/presign-upload"):
        return True
    if path.startswith("/api/internal/workflow/") and method != "GET":
        return True
    if path.startswith("/admin/api/v1/ai/"):
        return method != "GET" or path.rstrip("/") == "/admin/api/v1/ai/voices"
    if path.startswith("/admin/api/v1/cos/"):
        return method != "GET" or path not in (
            "/admin/api/v1/cos/config", "/admin/api/v1/cos/status", "/admin/api/v1/cos/move-preview"
        )
    if path.startswith("/admin/api/v1/tunnel/"):
        return method != "GET"
    if path in ("/admin/api/v1/assistant/execute", "/admin/api/v1/assistant/plan"):
        return True
    if ("trigger" in path or "/retry" in path or path.endswith("/generate-prompts")
            or "recommend" in path or "ai-generate" in path or "pick-preview" in path):
        return True
    if path.startswith("/admin/api/v1/about/upgrade") or path == "/admin/api/v1/about/check-update":
        return True
    if path.startswith("/admin/api/v1/system/ffmpeg-install"):
        return True
    if path in ("/admin/api/v1/materials/import-url", "/admin/api/v1/materials/import-cos",
                "/admin/api/v1/materials/share", "/admin/api/v1/notification/test",
                "/admin/api/v1/ebooks/draft-material"):
        return True
    if path.endswith("/resend"):
        return True
    return False


def _is_destructive(method: str, path: str) -> bool:
    """会破坏夹具/沙箱状态的管理端写操作，不进入批量流量（避免污染后续样本）。"""
    if not path.startswith("/admin/"):
        return False
    if method == "GET":
        return False
    if method == "DELETE":
        return True
    keywords = (
        "/backups", "/cleanup", "/restore", "/progress/reset", "/cancel",
        "index/rebuild", "emergency/", "batch-delete", "maintenance/tasks",
        "/db-admin/", "/publish", "/reset", "/rebuild", "/regenerate",
    )
    return any(k in path for k in keywords)


def build_cases(fixtures: dict) -> list[dict]:
    rows = json.loads(INVENTORY.read_text(encoding="utf-8"))
    cases = []
    for r in rows:
        method, path = r["method"], r["path"]
        cpath = path
        if path == "/api/v1/courses/{channel_id}/progress":
            # 课程进度只接受 course 类型频道，用新闻频道会 404（非缺陷）
            cpath = path.replace("{channel_id}", str(fixtures["course_channel_id"]))
        for name, value in fixtures.items():
            cpath = cpath.replace("{" + name + "}", str(value))
        # 未命名占位符统一填 999999（触发 404 校验路径，避免误删真实数据）
        import re
        cpath = re.sub(r"\{[^}]+\}", "999999", cpath)

        params = {}
        for p in r["params"]:
            if p["in"] == "query" and p["name"] in fixtures and p.get("required"):
                params[p["name"]] = fixtures[p["name"]]
        required_defaults = {"provider": "edge", "direction": "asc", "prefix": "perf/",
                             "confirm_text": "perf", "source": "rss"}
        for p in r["params"]:
            if p["in"] == "query" and p.get("required") and p["name"] not in params:
                params[p["name"]] = required_defaults.get(p["name"], fixtures["missing_id"])
        # 常用可选参数补默认值，让读路径尽量走真实分支
        for name in ("page", "size", "limit", "channel_type", "sort_order", "range", "category", "order_dir", "order_by", "format", "expired"):
            if any(p["name"] == name and p["in"] == "query" for p in r["params"]) and name not in params:
                params[name] = {
                    "page": 1, "size": 10, "limit": 10, "channel_type": "news",
                    "sort_order": "desc", "range": "7d", "category": "", "order_dir": "desc",
                    "order_by": "id", "format": "csv", "expired": 60,
                }[name]

        body = None
        coverage = "read" if method == "GET" else "validation"
        expected = [200] if method == "GET" else [400, 404, 422]
        # 产物/任务类 GET 用合成 ID 探测，资源尚未生成时 404 属预期（5xx 仍计缺陷）
        if method == "GET" and ("/audio/" in path or "/tasks/" in path):
            expected = [200, 404]
        body_map = {
            "POST /api/v1/playlogs/progress": {"episode_id": fixtures["episode_id"], "position": 10, "duration": 60, "completed": False, "listened_seconds": 10},
            "POST /api/v1/favorites": {"episode_id": fixtures["episode_id"]},
            "POST /api/v1/feedbacks": {"category": "other", "content": "性能测试基线反馈内容，请忽略。", "contact": None},
            "POST /api/v1/comments": {"episode_id": fixtures["episode_id"], "content": "性能测试基线评论", "user_name": "性能测试用户", "user_avatar": None},
            "PUT /api/v1/users/profile": {"nickname": "性能测试用户"},
            "POST /api/v1/client/report": {"category": "perf", "message": "baseline", "payload": {}, "client_ts": 0},
            "POST /api/v1/subscriptions/message": {"template_id": str(fixtures["template_id"])},
            "POST /api/v1/comments/{comment_id}/like": None,
            "DELETE /api/v1/comments/{comment_id}/like": None,
            "POST /api/v1/subscriptions/channels/{channel_id}": None,
            "DELETE /api/v1/subscriptions/channels/{channel_id}": None,
            "DELETE /api/v1/favorites/{episode_id}": None,
            "DELETE /api/v1/account/data": {"confirm": False},
            "POST /admin/api/v1/m/device/register": {"device_id": "perf-device", "platform": "web", "app_version": "perf"},
            "POST /admin/api/v1/m/push/register": {"device_fingerprint": "perf-device", "push_token": "perf-token", "platform": "web"},
            "POST /admin/api/v1/m/inbox/mark-read": {"ids": []},
            "POST /admin/api/v1/workflows/batch-delete/preview": {"workflow_ids": []},
            "POST /admin/api/v1/db-admin/tables/{table}/cascade-preview": {"pk_value": fixtures["pk_value"]},
        }
        key = f"{method} {path}"
        if key in body_map:
            body = body_map[key]
            coverage = "write"
            expected = [200, 201, 204]
        elif method == "DELETE":
            coverage = "write"
            expected = [200, 201, 204, 404]
        external = _is_external(method, path)
        sse = path == "/admin/api/v1/events/stream"
        destructive = _is_destructive(method, path) and not external
        multipart = "multipart/form-data" in (r.get("request_body") or [])
        if multipart:
            # 文件上传端点需 multipart 体，JSON 夹具只覆盖参数校验路径
            coverage = "validation"
            expected = [400, 415, 422]
        if external:
            coverage = "external"
            expected = list(range(100, 600))
        if sse:
            coverage = "sse"
        if destructive:
            coverage = "destructive"
            # 破坏性端点一律用不存在的 id：probe_all 会对带路径参数的 DELETE 真实发请求，
            # 沿用夹具 id 会把 material/channel 等共享夹具删掉，污染后续基线样本
            cpath = re.sub(r"\{[^}]+\}", "999999", path)
        if path.endswith("/login") and not external:
            coverage = "probe"
        cases.append({
            "group": r["group"], "method": method, "path": path, "case_path": cpath,
            "label": f"{method} {path}", "params": params, "body": body,
            "coverage": coverage, "expected": expected, "tags": r["tags"],
            "external": external, "sse": sse, "destructive": destructive,
            "execute_baseline": not (external or sse or destructive),
        })
    return cases


def main() -> int:
    if not DB.exists():
        raise SystemExit("沙箱库不存在，请先执行 sandbox.py prepare")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    try:
        user_id = get_or_create_user(conn)
        admin_id, admin_password = get_or_create_admin(conn)
        feedback_id = ensure_feedback(conn, user_id)
        fixtures = build_fixtures(conn, user_id, admin_id, feedback_id)
    finally:
        conn.close()

    from app.core.security import create_access_token

    c_token, c_jti, _ = create_access_token(str(user_id), token_type="user")
    a_token, a_jti, _ = create_access_token(
        str(admin_id), token_type="admin",
        extra_claims={"role": "admin", "username": ADMIN_USERNAME},
    )
    internal_token = ""
    env_path = SANDBOX_BACKEND / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("INTERNAL_API_TOKEN="):
            internal_token = line.split("=", 1)[1].split("  #")[0].strip().strip('"').strip("'")

    (RUNTIME / "tokens.json").write_text(json.dumps({
        "c_token": c_token, "admin_token": a_token,
        "internal_token": internal_token,
        "c_user_id": user_id, "admin_id": admin_id, "admin_password": admin_password,
        "c_jti": c_jti, "admin_jti": a_jti,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUNTIME / "fixtures.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")

    cases = build_cases(fixtures)
    for c in cases:
        if c["path"] in ("/api/v1/auth/logout", "/admin/api/v1/auth/logout"):
            # 登出会吊销当前 token，基线批量里执行会打断后续请求；改为独立探针
            c["execute_baseline"] = False
            c["coverage"] = "probe"
        if c["path"] == "/admin/api/v1/auth/login":
            # 明文凭据只留在 runtime/（已被 gitignore），用例体里放哨兵：
            # gen_jmx 转成 JMeter 属性占位、probe_all 发请求时再从 tokens.json 还原
            c["body"] = {"username": ADMIN_USERNAME, "password": SENTINEL_ADMIN_PASSWORD}
            c["coverage"] = "write"
            c["expected"] = [200]
    (RUNTIME / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    counts = Counter(c["coverage"] for c in cases)
    print(f"[ok] 账号：C user_id={user_id}，admin id={admin_id}")
    print(f"[ok] 用例 {len(cases)} 条：{dict(counts)}")
    print(f"[ok] 夹具：{fixtures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
