"""本次 8 项修复的 API 集成测试。

覆盖任务 5/7/8 的后端集成验证：
- 任务5：播放计数器（position >= PLAY_COUNT_THRESHOLD_SEC 时 +1）
- 任务7：累计收听时间（listened_seconds 累加到 User.total_listen_duration，/stats 返回）
- 任务8：微信登录接口契约（空 code/缺 code 字段的参数校验）

与 test_play_service.py 的区别：前者是 service 层单元测试，本文件是路由层集成测试，
通过 TestClient 走完整 HTTP 链路，验证鉴权、参数解析、响应结构。

用 async def 是因为 db_session.commit() 是协程，需要 await；
TestClient 虽是同步客户端，但可在 async 测试函数中调用（内部兼容嵌套事件循环）。
"""
from datetime import date

import pytest

from app.core.security import create_access_token


async def _seed_user_and_episode(db_session, name_prefix="ch"):
    """预置 User + Channel + Episode（status=published），返回 (user, episode)。

    Episode 模型要求 date/duration/title/audio_url/channel_id 非 null；
    progress 路由校验 episode.status=='published'，否则返回 404。
    User 必须先落库才能让 token 中的 user_id 与统计字段关联。
    """
    from app.models import Episode, Channel, User
    user = User(openid=f"openid-{name_prefix}", nickname=f"用户-{name_prefix}")
    db_session.add(user)
    await db_session.commit()

    channel = Channel(name=f"频道-{name_prefix}")
    db_session.add(channel)
    await db_session.commit()

    episode = Episode(
        title=f"节目-{name_prefix}",
        channel_id=channel.id,
        audio_url="http://x/y.mp3",
        duration=120,
        date=date.today(),
        status="published",  # 路由层 _get_published_episode 校验
    )
    db_session.add(episode)
    await db_session.commit()
    return user, episode


def _user_headers(user_id):
    """生成指向 user_id 的 C 端 token 头。"""
    token, _, _ = create_access_token(str(user_id), token_type="user")
    return {"Authorization": f"Bearer {token}"}


class TestPlaylogProgress:
    """任务5：播放进度上报接口集成测试。

    progress 路由依赖 get_current_user（必须带 token），
    且校验 episode.status=='published'（必须预置已发布节目）。
    """

    @pytest.mark.asyncio
    async def test_progress_below_threshold_returns_ok(self, client, db_session):
        """position < 30 时接口返回 200 + code=0（不触发计数，service 层已测）。"""
        user, episode = await _seed_user_and_episode(db_session, "A")

        resp = client.post(
            "/api/v1/playlogs/progress",
            json={
                "episode_id": episode.id,
                "position": 10,  # < 30 阈值
                "duration": 120,
                "completed": False,
            },
            headers=_user_headers(user.id),
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_progress_above_threshold_returns_ok(self, client, db_session):
        """position >= 30 时接口返回 200 + code=0（触发计数，service 层已测）。"""
        user, episode = await _seed_user_and_episode(db_session, "B")

        resp = client.post(
            "/api/v1/playlogs/progress",
            json={
                "episode_id": episode.id,
                "position": 35,  # >= 30 阈值
                "duration": 120,
                "completed": False,
            },
            headers=_user_headers(user.id),
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_progress_with_listened_seconds_accumulates(self, client, db_session):
        """任务7：listened_seconds 参数累加到 User.total_listen_duration。"""
        user, episode = await _seed_user_and_episode(db_session, "C")
        headers = _user_headers(user.id)

        # 第一次上报 listened_seconds=25
        r1 = client.post(
            "/api/v1/playlogs/progress",
            json={
                "episode_id": episode.id,
                "position": 25,
                "duration": 120,
                "completed": False,
                "listened_seconds": 25,
            },
            headers=headers,
        )
        assert r1.status_code == 200

        # 第二次上报 listened_seconds=40
        r2 = client.post(
            "/api/v1/playlogs/progress",
            json={
                "episode_id": episode.id,
                "position": 65,
                "duration": 120,
                "completed": False,
                "listened_seconds": 40,
            },
            headers=headers,
        )
        assert r2.status_code == 200

        # 刷新 user，验证 total_listen_duration 已累加 25+40=65
        await db_session.refresh(user)
        assert user.total_listen_duration == 65, (
            f"期望 65，实际 {user.total_listen_duration}，listened_seconds 应累加"
        )

    def test_progress_unauthorized_without_token(self, client):
        """无 token 访问 /playlogs/progress 应返回 401。"""
        resp = client.post(
            "/api/v1/playlogs/progress",
            json={"episode_id": 1, "position": 10, "duration": 120},
        )
        assert resp.status_code == 401


class TestUserStats:
    """任务7：用户统计接口测试。"""

    @pytest.mark.asyncio
    async def test_stats_returns_total_listen_duration(self, client, db_session):
        """/users/stats 的 total_listen_seconds 应来自 User.total_listen_duration 字段。"""
        from app.models import User
        user = User(
            openid="test-fix-002",
            nickname="统计用户",
            total_listen_duration=3600,  # 60 分钟
            total_listen_count=5,
        )
        db_session.add(user)
        await db_session.commit()

        resp = client.get("/api/v1/users/stats", headers=_user_headers(user.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        # total_listen_seconds 应等于 User.total_listen_duration（3600 秒）
        assert data["total_listen_seconds"] == 3600, (
            f"期望 3600，实际 {data['total_listen_seconds']}，"
            "应来自 User.total_listen_duration 而非 sum(PlayProgress.position)"
        )
        assert data["total_listen_episodes"] == 5

    @pytest.mark.asyncio
    async def test_stats_zero_when_no_listen_history(self, client, db_session):
        """无收听记录的用户统计应为 0，不报错。"""
        from app.models import User
        user = User(openid="test-fix-003", nickname="新用户")
        db_session.add(user)
        await db_session.commit()

        resp = client.get("/api/v1/users/stats", headers=_user_headers(user.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["total_listen_seconds"] == 0
        assert body["data"]["total_listen_episodes"] == 0

    def test_stats_unauthorized_without_token(self, client):
        """无 token 访问 /users/stats 应返回 401。"""
        resp = client.get("/api/v1/users/stats")
        assert resp.status_code == 401


class TestAuthLoginContract:
    """任务8：微信登录接口契约测试（不实际调用微信 API）。

    注意：项目自定义异常处理器把 RequestValidationError 转为 HTTP 400 + code=400，
    所以空 code / 缺 code 都返回 400 而非 FastAPI 默认的 422。
    """

    def test_login_empty_code_returns_400(self, client):
        """空 code 违反 min_length=1 约束，返回 400（自定义处理器转换）。"""
        resp = client.post("/api/v1/auth/login", json={"code": ""})
        assert resp.status_code == 400

    def test_login_missing_code_field_returns_400(self, client):
        """缺少 code 字段返回 400（自定义处理器转换）。"""
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 400


class TestUserProfile:
    """任务8：用户资料更新接口测试（PUT /users/profile）。

    覆盖头像/昵称写回后端 User 表的完整链路：
    前端 onConfirmEditProfile 调 updateUserProfile → 后端 update_profile → User.nickname/avatar 字段持久化。
    这是"微信资料未生效"问题的关键验证点：后端必须正确保存前端提交的资料。
    """

    @pytest.mark.asyncio
    async def test_update_nickname_and_avatar(self, client, db_session):
        """同时更新昵称和头像 URL，后端 User 表字段正确持久化。"""
        user, _ = await _seed_user_and_episode(db_session, "D")
        headers = _user_headers(user.id)

        resp = client.put(
            "/api/v1/users/profile",
            json={
                "nickname": "新昵称D",
                "avatar": "http://127.0.0.1:8000/avatars/1_1700000000.jpg",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        data = resp.json()["data"]
        assert data["user"]["nickname"] == "新昵称D"
        assert data["user"]["avatar"].endswith("1_1700000000.jpg")

        # 刷新 ORM 对象，验证字段已落库
        await db_session.refresh(user)
        assert user.nickname == "新昵称D"
        assert user.avatar.endswith("1_1700000000.jpg")

    @pytest.mark.asyncio
    async def test_update_nickname_only(self, client, db_session):
        """仅更新昵称（avatar 不下发），已有头像不被覆盖为空。"""
        from app.models import User
        user = User(
            openid="test-profile-avatar",
            nickname="旧昵称",
            avatar="http://127.0.0.1:8000/avatars/old.jpg",
        )
        db_session.add(user)
        await db_session.commit()

        resp = client.put(
            "/api/v1/users/profile",
            json={"nickname": "新昵称E"},
            headers=_user_headers(user.id),
        )
        assert resp.status_code == 200
        # avatar 未下发，后端不覆盖，保持旧值
        await db_session.refresh(user)
        assert user.nickname == "新昵称E"
        assert user.avatar == "http://127.0.0.1:8000/avatars/old.jpg"

    @pytest.mark.asyncio
    async def test_update_avatar_only(self, client, db_session):
        """仅更新头像（nickname 不下发），已有昵称不被覆盖。"""
        from app.models import User
        user = User(openid="test-profile-nick", nickname="保留昵称", avatar=None)
        db_session.add(user)
        await db_session.commit()

        resp = client.put(
            "/api/v1/users/profile",
            json={"avatar": "http://127.0.0.1:8000/avatars/new.jpg"},
            headers=_user_headers(user.id),
        )
        assert resp.status_code == 200
        await db_session.refresh(user)
        assert user.avatar == "http://127.0.0.1:8000/avatars/new.jpg"
        # nickname 未下发，保持旧值
        assert user.nickname == "保留昵称"

    def test_update_profile_unauthorized_without_token(self, client):
        """无 token 访问 PUT /users/profile 返回 401。"""
        resp = client.put("/api/v1/users/profile", json={"nickname": "x"})
        assert resp.status_code == 401


class TestUserAvatar:
    """任务8：头像上传接口测试（POST /users/avatar）。

    覆盖 wx.uploadFile → 后端持久化 → 返回 /avatars/{filename} URL 的完整链路。
    前端 uploadAvatar 拿到 URL 后再调 PUT /users/profile 写回 User.avatar。
    """

    @pytest.mark.asyncio
    async def test_upload_avatar_success(self, client, db_session, tmp_path, monkeypatch):
        """上传合法 jpg 图片，返回 /avatars/{filename} URL。"""
        from io import BytesIO
        import app.routers.api.users as users_router

        # 重定向头像落盘到临时目录：① 避免污染真实 data/avatars；
        # ② 临时目录位于 OS TEMP 下，safe-delete 守卫允许清理——
        # 否则全量运行时 saved.unlink 被守卫拦截（SAFE_DELETE_FAIL_CLOSED）导致用例失败。
        avatar_dir = tmp_path / "avatars"
        avatar_dir.mkdir()
        monkeypatch.setattr(users_router, "resolve_avatar_dir", lambda: avatar_dir)

        user, _ = await _seed_user_and_episode(db_session, "F")
        headers = _user_headers(user.id)

        # 构造合法 jpg 文件（后端仅校验扩展名 + content_type，不校验图片内容）
        fake_jpg = BytesIO(b"\xff\xd8\xff\xe0fake_jpeg_data")
        resp = client.post(
            "/api/v1/users/avatar",
            files={"file": ("avatar.jpg", fake_jpg, "image/jpeg")},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        url = resp.json()["data"]["url"]
        # URL 格式：/avatars/{user_id}_{timestamp}.jpg
        assert url.startswith("/avatars/")
        assert url.endswith(".jpg")
        assert f"{user.id}_" in url

        # 验证文件已写入磁盘（落盘到临时目录，断言与实际写入路径一致）
        filename = url.split("/")[-1]
        saved = avatar_dir / filename
        assert saved.exists(), f"头像文件应写入磁盘: {saved}"
        # 清理测试文件（临时目录，守卫允许删除）
        saved.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_upload_avatar_rejects_invalid_extension(self, client, db_session):
        """非法扩展名（.exe）被拒绝，业务 code=400。"""
        from io import BytesIO

        user, _ = await _seed_user_and_episode(db_session, "G")
        headers = _user_headers(user.id)

        fake_exe = BytesIO(b"MZfake_executable")
        resp = client.post(
            "/api/v1/users/avatar",
            files={"file": ("malware.exe", fake_exe, "application/octet-stream")},
            headers=headers,
        )
        # 项目统一响应模式：BizError 返回 HTTP 200 + JSON code=400（业务错误码）
        # http_status 默认 200，业务错误通过 body.code 区分，不依赖 HTTP 状态码
        assert resp.status_code == 200
        assert resp.json()["code"] == 400

    def test_upload_avatar_unauthorized_without_token(self, client):
        """无 token 访问 POST /users/avatar 返回 401。"""
        from io import BytesIO

        fake = BytesIO(b"\xff\xd8\xff\xe0fake")
        resp = client.post(
            "/api/v1/users/avatar",
            files={"file": ("a.jpg", fake, "image/jpeg")},
        )
        assert resp.status_code == 401
