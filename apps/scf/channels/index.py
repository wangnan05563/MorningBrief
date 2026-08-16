"""云函数：频道列表（GET /api/v1/channels）。

数据来源：COS 对象 channels.json（由后端 publish_service 发布）。
- 文件存在：返回活跃频道列表
- 文件不存在：返回默认频道 [{id: "", name: "全部"}]，保证小程序始终能展示频道 tab

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

# 默认频道：仅"全部"，channel_id 为空字符串
# 小程序点击"全部"时不传 channel_id，SCF 端返回所有节目（兼容无频道旧数据）
_DEFAULT_CHANNELS = [{"id": "", "name": "全部"}]


def handler(event, context):
    """SCF 入口：返回频道列表。"""
    # 1. 验证 token（C 端接口需登录）
    try:
        verify_token(event)
    except Exception as e:
        return error_response(str(e), status_code=401)

    # 2. 从 COS 读取 channels.json
    try:
        response = cos_client.get_object(Bucket=COS_BUCKET, Key="channels.json")
        body = response["Body"].read().decode("utf-8")
        channels = json.loads(body)
    except Exception:
        # channels.json 不存在（后端未发布或首次部署），返回默认频道
        return json_response(_DEFAULT_CHANNELS)

    # 3. 校验数据格式：必须是 list 且非空，否则回退默认频道
    if not isinstance(channels, list) or not channels:
        return json_response(_DEFAULT_CHANNELS)

    return json_response(channels)
