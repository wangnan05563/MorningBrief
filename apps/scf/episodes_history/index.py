"""云函数：历史节目列表（GET /api/v1/episodes/history）。

数据来源：COS 对象 episodes/index.json（最近 N 期节目索引）。
支持 page/size 分页（默认 size=20）。

与单机 exe 解耦：SCF 仅读 COS，不访问 SQLite。
"""
import json

from scf.common.handler_base import (
    COS_BUCKET,
    cos_client,
    error_response,
    json_response,
    parse_query,
    verify_token,
)


def handler(event, context):
    """SCF 入口：返回历史节目分页列表。"""
    # 1. 验证 token
    try:
        verify_token(event)
    except Exception as e:
        return error_response(str(e), status_code=401)

    # 2. 解析分页参数
    query = parse_query(event)
    try:
        page = int(query.get("page", "1"))
        size = int(query.get("size", "20"))
    except ValueError:
        return error_response("page/size 必须为整数", status_code=400)
    if page < 1 or size < 1:
        return json_response({"total": 0, "list": []})

    # 3. 从 COS 读取节目索引
    try:
        response = cos_client.get_object(Bucket=COS_BUCKET, Key="episodes/index.json")
        body = response["Body"].read().decode("utf-8")
        index_data = json.loads(body)
    except Exception:
        # 索引不存在时返回空列表
        return json_response({"total": 0, "list": []})

    episodes = index_data.get("episodes", [])
    total = len(episodes)
    offset = (page - 1) * size
    page_list = episodes[offset:offset + size]

    return json_response({"total": total, "list": page_list})
