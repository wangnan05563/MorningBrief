"""云函数：用户反馈提交（POST /api/v1/feedbacks）。

数据流：写 COS 对象 feedbacks/{yyyymmdd}/{feedback_id}.json，
单机 exe 的发布服务（publish_service）定时同步到 SQLite feedback 表后删除 COS 对象。

与单机 exe 解耦：SCF 仅写 COS，不访问 SQLite。
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
    verify_token,
)


def handler(event, context):
    """SCF 入口：提交用户反馈。"""
    try:
        payload = verify_token(event)
    except Exception as e:
        return error_response(str(e), status_code=401)

    user_id = int(payload["sub"])

    try:
        body = parse_body(event)
    except json.JSONDecodeError:
        return error_response("请求体格式错误", status_code=400)

    content = (body.get("content") or "").strip()
    category = (body.get("category") or "other").strip()
    if not content:
        return error_response("反馈内容不能为空", status_code=400)

    # 生成反馈对象：feedbacks/{yyyymmdd}/{feedback_id}.json
    yyyymmdd = datetime.now(timezone.utc).strftime("%Y%m%d")
    feedback_id = uuid.uuid4().hex
    feedback_payload = {
        "feedback_id": feedback_id,
        "user_id": user_id,
        "category": category,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    key = f"feedbacks/{yyyymmdd}/{feedback_id}.json"
    cos_client.put_object(
        Bucket=COS_BUCKET,
        Key=key,
        Body=json.dumps(feedback_payload, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )

    return json_response({"feedback_id": feedback_id, "success": True})
