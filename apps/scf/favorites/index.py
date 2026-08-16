"""云函数：用户收藏管理（GET/POST/DELETE /api/v1/favorites）。

承载三个 C 端接口：
- GET /favorites：查询当前用户收藏列表
- POST /favorites：添加收藏（请求体 { episode_id: int }）
- DELETE /favorites/{episode_id}：取消收藏

数据流：读写 COS 对象 favorites/{user_id}/index.json（每用户一个索引文件），
单机 exe 的 APScheduler 可定时聚合到本地 favorite 表作为快照。

与单机 exe 解耦：SCF 仅读写 COS，不访问单机 SQLite。
"""
import json
from datetime import datetime, timezone

from scf.common.handler_base import (
    COS_BUCKET,
    cos_client,
    error_response,
    json_response,
    parse_body,
    verify_token,
)


def handler(event, context):
    """SCF 入口：根据 HTTP method 分发到查询/添加/取消。"""
    method = (event.get("httpMethod", "") or "").upper()

    try:
        payload = verify_token(event)
    except Exception as e:
        return error_response(str(e), status_code=401)

    # 用 sub 字符串作为 COS 路径标识，便于与 favorite 表 user_id（String(64)）对齐
    user_id = str(payload["sub"])

    if method == "GET":
        return _list_favorites(user_id)
    if method == "POST":
        return _add_favorite(event, user_id)
    if method == "DELETE":
        return _remove_favorite(event, user_id)
    return error_response(f"不支持的 method: {method}", status_code=405, code=4005)


def _favorites_key(user_id: str) -> str:
    """返回用户收藏索引对象的 COS Key。"""
    return f"favorites/{user_id}/index.json"


def _load_favorites(user_id: str) -> list:
    """读取用户收藏列表，对象不存在时返回空列表。"""
    try:
        resp = cos_client.get_object(Bucket=COS_BUCKET, Key=_favorites_key(user_id))
        data = json.loads(resp["Body"].read().decode("utf-8"))
        # 兼容历史数据：保证返回 list
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
    except Exception:
        # COS 读取失败（含对象不存在）视为空列表，不阻断 C 端读取
        return []
    return []


def _save_favorites(user_id: str, items: list) -> None:
    """写回用户收藏列表到 COS。"""
    cos_client.put_object(
        Bucket=COS_BUCKET,
        Key=_favorites_key(user_id),
        Body=json.dumps(items, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def _list_favorites(user_id: str) -> dict:
    """查询收藏列表：返回 [{episode_id, created_at}, ...]。"""
    items = _load_favorites(user_id)
    # 按收藏时间倒序（最新收藏在前）
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return json_response({"items": items})


def _add_favorite(event: dict, user_id: str) -> dict:
    """添加收藏：去重后追加，写回 COS。"""
    try:
        body = parse_body(event)
    except json.JSONDecodeError:
        return error_response("请求体格式错误", status_code=400)

    episode_id = body.get("episode_id")
    if episode_id is None:
        return error_response("缺少 episode_id", status_code=400)
    try:
        episode_id = int(episode_id)
    except (TypeError, ValueError):
        return error_response("episode_id 必须为整数", status_code=400)

    items = _load_favorites(user_id)
    # 去重：已存在则仅更新收藏时间，避免重复条目
    for it in items:
        if it.get("episode_id") == episode_id:
            it["created_at"] = datetime.now(timezone.utc).isoformat()
            try:
                _save_favorites(user_id, items)
            except Exception:
                return error_response("收藏写入失败", status_code=500, code=5000)
            return json_response({"success": True, "episode_id": episode_id})

    items.append(
        {
            "episode_id": episode_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        _save_favorites(user_id, items)
    except Exception:
        return error_response("收藏写入失败", status_code=500, code=5000)

    return json_response({"success": True, "episode_id": episode_id})


def _remove_favorite(event: dict, user_id: str) -> dict:
    """取消收藏：从列表移除指定 episode_id，写回 COS。"""
    path_params = event.get("pathParameters", {}) or {}
    episode_id_raw = (
        path_params.get("episode_id")
        or path_params.get("id", "")
    )
    try:
        episode_id = int(episode_id_raw)
    except (TypeError, ValueError):
        return error_response("episode_id 必须为整数", status_code=400)

    items = _load_favorites(user_id)
    new_items = [it for it in items if it.get("episode_id") != episode_id]

    # 列表未变化时直接返回成功，避免无谓的 COS 写入
    if len(new_items) == len(items):
        return json_response({"success": True, "episode_id": episode_id})

    try:
        if new_items:
            _save_favorites(user_id, new_items)
        else:
            # 列表为空时删除对象，避免残留空文件占用 COS
            cos_client.delete_object(Bucket=COS_BUCKET, Key=_favorites_key(user_id))
    except Exception:
        return error_response("取消收藏失败", status_code=500, code=5000)

    return json_response({"success": True, "episode_id": episode_id})
