"""验证今日节目的 audio_url 是否指向 COS。"""
import json
import sys
import urllib.request

token_path = r"d:\code\otherProjects\20_News\jmeter_test\test_token.txt"
with open(token_path, "r", encoding="utf-8") as f:
    token = f.read().strip()

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/episodes/today",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode("utf-8"))

print(f"业务码: {data.get('code')}")
# data 可能是 dict 或 list
d = data.get("data")
if isinstance(d, dict):
    eps = d.get("list") or [d]
elif isinstance(d, list):
    eps = d
else:
    eps = []

print(f"节目数: {len(eps)}")
print()
for i, ep in enumerate(eps, 1):
    title = ep.get("title", "")[:50]
    url = ep.get("audio_url", "")
    print(f"[{i}] {title}")
    print(f"    audio_url: {url}")
    if "myqcloud.com" in url:
        print(f"    ✅ 已指向 COS")
    elif "ts.net" in url:
        print(f"    ⚠️  仍指向 Tailscale Funnel（历史音频未迁移）")
    elif url:
        print(f"    ℹ️  其他来源")
    print()
