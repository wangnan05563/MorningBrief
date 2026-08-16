"""云函数：节目详情（GET /api/v1/episodes/{id}）。

数据来源：COS 对象 episodes/{yyyymmdd}/meta.json（单期节目元数据，含稿件+分段）。

路径参数：episode_id（数字 ID）。先读 episodes/index.json 查找该 ID 对应的日期，
再读 episodes/{yyyymmdd}/meta.json 拿详情。
"""
import json

from scf.common.handler_base import (
    COS_BUCKET,
    cos_client,
    error_response,
    json_response,
    verify_token,
)


def handler(event, context):
    """SCF 入口：返回节目详情。"""
    # 1. 验证 token
    try:
        verify_token(event)
    except Exception as e:
        return error_response(str(e), status_code=401)

    # 2. 从 pathParameters 取 episode_id
    path_params = event.get("pathParameters", {}) or {}
    episode_id_raw = path_params.get("episode_id") or path_params.get("id", "")
    try:
        episode_id = int(episode_id_raw)
    except (TypeError, ValueError):
        return error_response("episode_id 必须为整数", status_code=400)

    # 3. 从索引查找该 ID 对应的日期
    try:
        resp = cos_client.get_object(Bucket=COS_BUCKET, Key="episodes/index.json")
        index_data = json.loads(resp["Body"].read().decode("utf-8"))
    except Exception:
        return error_response("节目不存在", status_code=404, code=4040)

    target = None
    for ep in index_data.get("episodes", []):
        if ep.get("id") == episode_id:
            target = ep
            break
    if target is None:
        return error_response("节目不存在", status_code=404, code=4040)

    # 4. 读 meta.json 拿详情
    yyyymmdd = target["date"].replace("-", "")
    meta_key = f"episodes/{yyyymmdd}/meta.json"
    try:
        resp = cos_client.get_object(Bucket=COS_BUCKET, Key=meta_key)
        meta = json.loads(resp["Body"].read().decode("utf-8"))
    except Exception:
        # meta 未生成时退回索引中的简要信息
        meta = target

    return json_response(meta)
