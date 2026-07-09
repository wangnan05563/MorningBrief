"""腾讯云 COS 客户端（V1.2 新增）。

用于：
- 音频文件上传（episodes/{date}/audio.mp3）
- JWT 黑名单对象（jwt_blacklist/{jti}.json）
- 播放进度对象（play_progress/{user_id}/{episode_id}.json）
- 节目元数据 JSON（episodes/today/{yyyymmdd}.json 等，供 SCF 读取）
"""
from app.cos.client import cos_client

__all__ = ["cos_client"]
