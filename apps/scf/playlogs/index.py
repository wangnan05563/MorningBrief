"""云函数：播放日志上报 + 进度查询。

承载两个 C 端接口：
- POST /api/v1/playlogs/progress：上报播放进度
- GET /api/v1/playlogs/progress/{episode_id}：查询播放进度

数据来源：
- 写：COS 对象 play_progress/{user_id}/{episode_id}.json（断点续播）+
       playlogs/{yyyymmdd}/{log_id}.json（异步日志，APScheduler 批量聚合到 SQLite）
- 读：COS 对象 play_progress/{user_id}/{episode_id}.json

与单机 exe 解耦：SCF 仅写 COS，单机 exe 的 APScheduler 定时拉取 playlogs/ 聚合到 SQLite。
"""
import json
import uuid
from datetime import datetime, timezone

from scf.common.handler_base import (
    COS_BUCKET,
    cos_client,
    error_response,
    json_response,
    parse_body,
    parse_query,
    verify_token,
)


def handler(event, context):
    """SCF 入口：根据 HTTP method 分发到上报/查询。"""
    method = (event.get("httpMethod", "") or "").upper()

    try:
        payload = verify_token(event)
    except Exception as e:
        return error_response(str(e), status_code=401)

    user_id = int(payload["sub"])

    if method == "POST":
        return _report_progress(event, user_id)
    if method == "GET":
        return _get_progress(event, user_id)
    return error_response(f"不支持的 method: {method}", status_code=405, code=4005)


def _report_progress(event: dict, user_id: int) -> dict:
    """上报播放进度：写 play_progress/ + playlogs/ 两个 COS 对象。"""
    try:
        body = parse_body(event)
    except json.JSONDecodeError:
        return error_response("请求体格式错误", status_code=400)

    episode_id = body.get("episode_id")
    position = body.get("position")
    duration = body.get("duration")
    completed = bool(body.get("completed", False))
    if episode_id is None or position is None or duration is None:
        return error_response("缺少 episode_id/position/duration", status_code=400)

    now_iso = datetime.now(timezone.utc).isoformat()
    completed_flag = 1 if completed else 0

    # 1. 写 play_progress（断点续播主路径，C 端下次进入时直接读此对象）
    progress_payload = {
        "user_id": user_id,
        "episode_id": episode_id,
        "position": position,
        "duration": duration,
        "completed": completed_flag,
        "updated_at": now_iso,
    }
    progress_key = f"play_progress/{user_id}/{episode_id}.json"
    cos_client.put_object(
        Bucket=COS_BUCKET,
        Key=progress_key,
        Body=json.dumps(progress_payload).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )

    # 2. 写 playlogs/{yyyymmdd}/{log_id}.json（异步日志，B 端 APScheduler 聚合）
    yyyymmdd = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_id = uuid.uuid4().hex
    log_payload = {
        "user_id": user_id,
        "episode_id": episode_id,
        "position": position,
        "duration": duration,
        "completed": completed_flag,
        "played_at": now_iso,
        "log_id": log_id,
    }
    log_key = f"playlogs/{yyyymmdd}/{log_id}.json"
    try:
        cos_client.put_object(
            Bucket=COS_BUCKET,
            Key=log_key,
            Body=json.dumps(log_payload).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
    except Exception:
        # 日志写入失败不阻断进度上报（断点续播已写）
        pass

    return json_response({"success": True})


def _get_progress(event: dict, user_id: int) -> dict:
    """查询播放进度：读 play_progress/{user_id}/{episode_id}.json。"""
    # episode_id 从 path 参数取，兼容 SCF 网关两种命名
    path_params = event.get("pathParameters", {}) or {}
    episode_id_raw = (
        path_params.get("episode_id")
        or path_params.get("id")
        or parse_query(event).get("episode_id", "")
    )
    try:
        episode_id = int(episode_id_raw)
    except (TypeError, ValueError):
        return error_response("episode_id 必须为整数", status_code=400)

    key = f"play_progress/{user_id}/{episode_id}.json"
    try:
        resp = cos_client.get_object(Bucket=COS_BUCKET, Key=key)
        data = json.loads(resp["Body"].read().decode("utf-8"))
        return json_response(data)
    except Exception:
        # 进度对象不存在（首次播放）返回 null
        return json_response(None)
