"""FTS5 搜索接口测试。"""
import json
import urllib.parse
import urllib.request

token_path = r"d:\code\otherProjects\20_News\jmeter_test\test_token.txt"
with open(token_path, "r", encoding="utf-8") as f:
    token = f.read().strip()

keywords = ["科技", "新闻", "AI", "今日", "早间"]

print("=" * 60)
print("FTS5 搜索接口测试")
print("=" * 60)

for kw in keywords:
    url = f"http://127.0.0.1:8000/api/v1/episodes/search?keyword={urllib.parse.quote(kw)}&page=1&size=5"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("data", {}).get("total", 0)
        items = data.get("data", {}).get("list", [])
        print(f"\n[关键词: {kw}] total={total}, 返回 {len(items)} 条")
        for item in items[:3]:
            print(f"  - {item.get('title', '')[:50]}")
    except Exception as e:
        print(f"\n[关键词: {kw}] FAIL: {e}")

# 测试特殊字符（应降级到 LIKE）
print(f"\n{'=' * 60}")
print("特殊字符降级测试")
print(f"{'=' * 60}")
for kw in ['"test"', "%abc%", "正常关键词"]:
    try:
        url = f"http://127.0.0.1:8000/api/v1/episodes/search?keyword={urllib.parse.quote(kw)}&page=1&size=5"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("data", {}).get("total", 0)
        print(f"  关键词 '{kw}' → total={total} ✅")
    except Exception as e:
        print(f"  关键词 '{kw}' → FAIL: {e} ❌")
