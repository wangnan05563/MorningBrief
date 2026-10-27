"""缓存键单源（T03322）。

键名此前在读写两侧各写一份字符串：C 端列表读的是 `...:v2`，`invalidate_list_cache()`
删的却是没有 `:v2` 的旧串——那是一个没人写入的键，于是后台改频道/调排序后，
小程序 tab 只能等 60s TTL 自愈。

键名只在这里定义，读写两侧同源 import：再加版本后缀时不存在「只改一半」的落点。
`backend/tests/test_t03322_channel_cache_key.py` 会扫描字面量，禁止键串在别处复现。
"""

# 管理端列表缓存（读：app/routers/admin/channels.py::list_channels）
CHANNELS_LIST_ALL = "channels:list:all"
CHANNELS_LIST_ACTIVE = "channels:list:active"

# C 端启用频道列表（读：app/routers/api/channels.py::list_channels）
# v2：cover_url/icon_url 改为绝对 URL 并新增 icon_url（小程序 <image> 不解析相对路径）
C_CHANNELS_LIST_ACTIVE = "api:channels:list_active:v2"
