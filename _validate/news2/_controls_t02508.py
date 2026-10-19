"""T02508 反证控制实验：每条新断言都要能"被弄坏就红"。

做法：把源码改坏 → 只跑对应那一条用例 → 期望它失败 → 还原。
还原放在 try/finally 里（历史上用 /tmp 备份失败过一次：Windows 侧看不见 Git-Bash 的 /tmp）。
"""
import io
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ADMIN = r"D:\code\otherProjects\20_News\apps\admin-web"

CONTROLS = [
    {
        "id": "C1",
        "desc": "删掉 LLM 指标页口径标注的 data-guide 锚点",
        "file": ADMIN + r"\src\views\stats\LlmMetrics.vue",
        "old": '<div data-guide="llm-metrics-scope" class="scope-note">',
        "new": '<div class="scope-note">',
        "test": "tests/llm-metrics.spec.js:94",
    },
    {
        "id": "C2",
        "desc": "后端没给起点时，前端拿当前时间冒充累计起点",
        "file": ADMIN + r"\src\views\stats\LlmMetrics.vue",
        "old": "startedAt: metrics.value.started_at,",
        "new": "startedAt: metrics.value.started_at || dayjs().format('YYYY-MM-DDTHH:mm:ss'),",
        "test": "tests/llm-metrics.spec.js:105",
    },
    {
        "id": "C3",
        "desc": "让日期选择器同时驱动趋势请求（即两个口径其实会互相影响）",
        "file": ADMIN + r"\src\views\stats\StatsOverview.vue",
        "old": '@change="loadOverview"',
        "new": '@change="() => { loadOverview(); loadTrend() }"',
        "test": "tests/stats.spec.js:223",
    },
    {
        "id": "C4",
        "desc": "把频道健康度的「仅趋势」说明删掉，回到只有一条没有刻度的线",
        "file": ADMIN + r"\src\views\stats\ChannelHealth.vue",
        "old": '<span class="trend-scope">仅趋势 · 未标刻度（悬停看条数）</span>',
        "new": '<span class="trend-scope"></span>',
        "test": "tests/channel-health.spec.js:77",
    },
]

results = []
for c in CONTROLS:
    with open(c["file"], "r", encoding="utf-8") as f:
        original = f.read()
    assert c["old"] in original, f'{c["id"]} 定位失败：{c["old"]}'
    mutated = original.replace(c["old"], c["new"], 1)
    try:
        with open(c["file"], "w", encoding="utf-8") as f:
            f.write(mutated)
        p = subprocess.run(
            f'npx playwright test "{c["test"]}" --reporter=line',
            cwd=ADMIN,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**__import__("os").environ, "PW_CHANNEL": "chrome"},
            timeout=600,
        )
        out = (p.stdout or "") + (p.stderr or "")
        failed = "1 failed" in out or p.returncode != 0
        results.append((c["id"], c["desc"], c["test"], p.returncode, failed,
                        [ln for ln in out.splitlines() if "passed" in ln or "failed" in ln][-1:]))
    finally:
        with open(c["file"], "w", encoding="utf-8") as f:
            f.write(original)
        with open(c["file"], "r", encoding="utf-8") as f:
            assert f.read() == original, f'{c["id"]} 还原失败！'

print("=" * 70)
ok = True
for cid, desc, test, rc, failed, tail in results:
    mark = "符合预期（改坏即红）" if failed else "！！断言不成立（改坏仍然绿）"
    if not failed:
        ok = False
    print(f'{cid} rc={rc} {mark}\n   破坏：{desc}\n   用例：{test}\n   结果：{tail}')
print("=" * 70)
print("总体：", "全部控制实验按预期失败 → 断言可证伪" if ok else "存在失控断言")
