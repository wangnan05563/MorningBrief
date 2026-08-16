"""云函数：今日节目（GET /api/v1/episodes/today）。

数据来源：COS 对象 episodes/index.json（最近 N 期节目索引）。
今日节目 = 索引中第一条（按 date 倒序），未发布时返回 null。

与单机 exe 解耦：SCF 仅读 COS，不访问 SQLite。
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
    """SCF 入口：返回今日节目。"""
    # 1. 验证 token（C 端接口需登录）
    try:
        verify_token(event)
    except Exception as e:
        return error_response(str(e), status_code=401)

    # 2. 从 COS 读取节目索引
    try:
        response = cos_client.get_object(Bucket=COS_BUCKET, Key="episodes/index.json")
        body = response["Body"].read().decode("utf-8")
        index_data = json.loads(body)
    except Exception:
        # 索引对象不存在（首次部署或全部删除），返回 null
        return json_response(None)

    # 3. 索引按 date 倒序，第一条即今日节目
    episodes = index_data.get("episodes", [])
    if not episodes:
        return json_response(None)

    today_episode = episodes[0]
    return json_response(today_episode)
