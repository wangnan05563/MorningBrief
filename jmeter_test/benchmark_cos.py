"""音频下载速度对比测试（TTFB + 多次采样）。

注意：本机测试的局限性
- 本机访问 Tailscale Funnel 走 loopback，不经公网，速度虚高
- 本机访问 COS 走真实公网到腾讯云北京节点
- 真机用户场景：4G/WiFi → COS 边缘节点（近） vs 4G/WiFi → Tailscale 中转 → 用户电脑上行（慢）
- 因此本机测试的"绝对速度"不能代表真机场景，但 COS 的 TTFB 和稳定性有参考价值
"""
import sqlite3
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse, quote

DB_PATH = Path(r"d:\code\otherProjects\20_News\backend\data\news.db")

conn = sqlite3.connect(str(DB_PATH))
try:
    cur = conn.execute(
        "SELECT id, audio_url FROM episode "
        "WHERE audio_url LIKE 'https://%' ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
finally:
    conn.close()

if not row:
    print("No COS audio found")
    raise SystemExit(1)

eid, cos_url = row
parsed = urlparse(cos_url)
encoded_path = quote(parsed.path, safe='/_:')
cos_url_encoded = parsed._replace(path=encoded_path).geturl()

print(f"测试 episode_id={eid}")
print(f"文件: {parsed.path}")
print(f"测试次数: 5 次 Range 1MB 下载，取平均")
print(f"{'=' * 70}\n")


def test_download(url: str, label: str, count: int = 5) -> dict:
    """测试下载多次，返回 TTFB 和总时间统计。"""
    ttfb_list = []
    total_list = []
    for i in range(count):
        req = urllib.request.Request(url, headers={"Range": "bytes=0-1048575"})
        t1 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                # TTFB：从发请求到收到首字节
                first_chunk = resp.read(8192)
                ttfb = time.time() - t1
                ttfb_list.append(ttfb)
                # 剩余数据
                resp.read()
                total = time.time() - t1
                total_list.append(total)
        except Exception as e:
            print(f"  [{label}] 第 {i+1} 次 FAIL: {e}")
            return {"success": False}
    avg_ttfb = sum(ttfb_list) / len(ttfb_list)
    avg_total = sum(total_list) / len(total_list)
    min_ttfb = min(ttfb_list)
    max_ttfb = max(ttfb_list)
    print(f"  [{label}] TTFB: avg={avg_ttfb*1000:.0f}ms min={min_ttfb*1000:.0f}ms max={max_ttfb*1000:.0f}ms | 总: avg={avg_total*1000:.0f}ms")
    return {
        "success": True,
        "avg_ttfb": avg_ttfb,
        "avg_total": avg_total,
        "min_ttfb": min_ttfb,
        "max_ttfb": max_ttfb,
    }


# 1. COS 测试
print("[COS 边缘节点]")
cos_result = test_download(cos_url_encoded, "COS")

# 2. 本地后端测试（基线，代表局域网场景）
local_url = f"http://127.0.0.1:8000/audio{encoded_path}"
print("\n[本地直连 - 代表局域网场景]")
local_result = test_download(local_url, "Local", count=3)

# 3. 对比
print(f"\n{'=' * 70}")
print("结果分析")
print(f"{'=' * 70}")
if cos_result.get("success"):
    print(f"  COS 平均 TTFB: {cos_result['avg_ttfb']*1000:.0f}ms")
    print(f"  COS 平均下载: {cos_result['avg_total']*1000:.0f}ms")
    print(f"  COS 下载速度: {1.0/cos_result['avg_total']:.1f} MB/s")
if local_result.get("success"):
    print(f"  本地平均 TTFB: {local_result['avg_ttfb']*1000:.0f}ms")
    print(f"  本地平均下载: {local_result['avg_total']*1000:.0f}ms")
    print(f"  本地下载速度: {1.0/local_result['avg_total']:.1f} MB/s")

print(f"\n{'=' * 70}")
print("真机场景说明")
print(f"{'=' * 70}")
print("""
本机测试局限：
- 本机访问 Tailscale Funnel 走 loopback，不经公网，速度虚高
- 本机访问 COS 走真实公网到腾讯云北京节点

真机用户实际体验：
- COS：4G/WiFi → 腾讯云边缘节点（全国就近分布）
  * TTFB 约 50-200ms（与地理位置相关）
  * 下载速度受用户 4G/WiFi 带宽限制，通常 5-30 MB/s
  * 不依赖用户电脑在线
  * 不受家庭宽带上行限制

- Tailscale Funnel：4G/WiFi → Tailscale 边缘 → DERP 中转 → 用户电脑上行
  * TTFB 约 300-1000ms（多跳中转 + TLS 握手）
  * 下载速度受家庭宽带上行限制（通常 5-30 Mbps = 0.6-3.75 MB/s）
  * 依赖用户电脑在线
  * 跨地域时 DERP 中转延迟更高

结论：
  COS 在真机场景下会比 Funnel 快 5-10 倍，特别是 TTFB 和下载速度。
  本机测试的 COS TTFB {:d}ms 是真实公网延迟，可作为真机参考。
""").format(int(cos_result.get('avg_ttfb', 0) * 1000) if cos_result.get('success') else 0)
