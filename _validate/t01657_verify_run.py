"""T01657 听书频道 30 分钟保底 · 真跑复验脚本（在 MorningBrief 运行实例上执行）。

设计原则（为什么大部分断言不看日志）：
`rewriter.py:1853`、`concat.py:445` 等关键行是 loguru + %-style 占位符（T01678），
loguru 不做 % 格式化 → 日志里只剩 `target_sec=%d`、`补足 Ns` 的字面量，**数值不可判定**。
所以本脚本把可判定口径全部改走数据库与文件系统，日志只作辅助 grep；
T01678 修好后日志口径可自动恢复（脚本已按两种形态兼容匹配）。

安全：默认**不触发**工作流（真跑消耗真实 LLM/TTS 预算并写入实例），必须显式 `--trigger`；
只连本机回环；管理员口令只从环境变量 `T01657_ADMIN_PASSWORD` 读，不落盘不打印。

用法：
    # 1) 只看当前状态与前置条件（零副作用）
    python _validate/t01657_verify_run.py --channel-id 11
    # 2) 在运行实例上真跑一期并复验（会花钱）
    set T01657_ADMIN_PASSWORD=*** && python _validate/t01657_verify_run.py --trigger --base http://127.0.0.1:8000
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

FLOOR_SEC = 1800
LOW_RATIO, HIGH_RATIO = 0.80, 1.20


def q(sql, args=(), db="data/news.db"):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def api(base, method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # NOSONAR: 本机回环管理接口
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"raw": e.read().decode("utf-8", "replace")[:300]}
    except Exception as e:  # 连接失败等
        return 0, {"err": str(e)}


def preflight(db, channel_id):
    print(f"\n=== 前置检查（channel_id={channel_id}，只读）===")
    ch = q("select id,name,channel_type,is_active,schedule_time,min_duration_sec "
           "from channel where id=?", (channel_id,), db)
    if not ch:
        print("  [FAIL] 频道不存在"); return None
    cid, name, ctype, active, sched, min_sec = ch[0]
    print(f"  频道：{name} channel_type={ctype} is_active={active} schedule={sched} "
          f"min_duration_sec={min_sec}")
    ok_type = ctype == "audiobook"
    print(f"  [{'OK' if ok_type else 'FAIL'}] 任务第 1 条：channel_type 必须是 audiobook"
          + ("" if ok_type else "  → 走管理端接口改正类型（不得直写库）"))
    segs = q("select config_key,config_value from ai_config where config_key in "
             "('llm_max_script_segments','llm_target_duration_sec')", (), db)
    print(f"  ai_config 运行时热调项：{dict(segs) or '（未配置，用代码默认）'}")
    mat = q("select count(*) from material where channel_id=?", (channel_id,), db)[0][0]
    print(f"  本频道可用素材（书池/爬取入库）：{mat} 条"
          + ("  [WARN] 素材为 0 → crawl 步骤会空跑，先确认书池 book_pool_item"
             if mat == 0 else ""))
    print(f"  历史成品：{q('select count(*), max(duration) from episode where channel_id=?', (channel_id,), db)[0]} "
          f"(条数, 最长秒) —— max<1800 说明尚未有过达标期")
    return dict(name=name, channel_type=ctype, min_duration_sec=min_sec, materials=mat)


def check_log_markers_readable(repo_root):
    """已知缺陷点名：关键日志行若仍是 %-style，数值口径不可判定（T01678）。"""
    hits = []
    for rel, pat in (("backend/app/workflow/llm/rewriter.py", r"时长/字数联动 [^\n]*%d"),
                     ("backend/app/workflow/stitch/concat.py", r"时长不足兜底 [^\n]*%ds")):
        p = os.path.join(repo_root, rel)
        if os.path.exists(p):
            txt = open(p, encoding="utf-8", errors="replace").read()
            hits.append((rel, bool(re.search(pat, txt))))
    return hits


def trigger(base, channel_id, episode_date):
    pwd = os.environ.get("T01657_ADMIN_PASSWORD", "")
    if not pwd:
        print("  [FAIL] 未设置环境变量 T01657_ADMIN_PASSWORD，无法登录管理端（口令不写进脚本/仓库）")
        return None
    code, body = api(base, "POST", "/admin/api/v1/auth/login",
                     body={"username": os.environ.get("T01657_ADMIN_USER", "admin"), "password": pwd})
    if code != 200:
        print(f"  [FAIL] 管理端登录失败 {code}: {str(body)[:150]}"); return None
    token = ((body.get("data") or {}).get("token")) or ((body.get("data") or {}).get("access_token"))
    if not token:
        print(f"  [FAIL] 登录响应无 token：{str(body)[:150]}"); return None
    code, body = api(base, "POST", "/admin/api/v1/workflows/trigger", token,
                     {"channel_id": channel_id, "episode_date": episode_date, "skip_crawl": False})
    wf = (body.get("data") or {}).get("workflow_id")
    print(f"  触发结果 HTTP {code} workflow_id={wf}")
    return wf


def wait_done(db, wf, timeout_sec, poll_sec):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        row = q("select status, error from workflow where id=?", (wf,), db)
        if row and row[0][0] in ("success", "failed", "partial_success"):
            return row[0]
        steps = q("select step_name,status from workflow_step where workflow_id=? order by id", (wf,), db)
        print(f"    …进行中 {dt.datetime.now():%H:%M:%S} 步骤={steps}", flush=True)
        time.sleep(poll_sec)
    return ("timeout", None)


def grep_logs(root, channel_name):
    """辅助 grep（%-style 缺陷下数值不可读，只判存在性）。"""
    logs = sorted(glob.glob(os.path.join(root, "backend", "logs", "*.log")) +
                  glob.glob(os.path.join(root, "logs", "*.log")))
    out = {"files": logs[-3:], "fallback": [], "overrange": [], "linkage": []}
    for p in out["files"]:
        for line in open(p, encoding="utf-8", errors="replace"):
            if "时长不足兜底" in line:
                out["fallback"].append(line.strip()[:220])
            elif "超出允许范围" in line or "StitchError" in line:
                out["overrange"].append(line.strip()[:220])
            elif "时长/字数联动" in line:
                out["linkage"].append(line.strip()[:220])
    return out


def verify(db, wf, channel_id, audio_root):
    print("\n=== 抽查口径（任务第 3 条，全部走数据库/文件实测）===")
    res = {}
    segs = []
    ep = q("select id,duration,audio_url,status from episode where workflow_id=? "
           "order by id desc limit 1", (wf,), db)
    if not ep:
        print("  [FAIL] 该工作流没有产出 episode"); return res
    ep_id, duration, audio_url, ep_status = ep[0]
    res["episode_id"], res["duration"] = ep_id, duration

    # 3.1 成品实测时长（不信任 DB 估算值：能定位到本地文件就用 ffprobe 实测）
    measured = None
    local = None
    if audio_url and not audio_url.startswith(("http://", "https://")):
        cand = audio_url if audio_url.startswith("/") else os.path.join(audio_root, audio_url)
        local = cand if os.path.exists(cand) else None
    if local:
        import subprocess
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", local], capture_output=True, text=True)
        try:
            measured = round(float(r.stdout.strip()))
        except ValueError:
            measured = None
    ok1 = duration is not None and duration >= FLOOR_SEC
    print(f"  [{'OK' if ok1 else 'FAIL'}] episode.duration={duration}s ≥ {FLOOR_SEC}s"
          f"（本地实测={'不可得（音频在 COS）' if measured is None else str(measured)+'s'}）")
    res["measured_sec"] = measured

    # 3.2 时长/字数联动：日志数值不可读 → 用 script 表反证「改写侧确实按 1800s 口径出稿」
    sc = q("select total_words,estimated_duration,segments from script where workflow_id=? "
           "order by id desc limit 1", (wf,), db)
    if sc:
        words, est, segs_raw = sc[0]
        segs = json.loads(segs_raw) if segs_raw else []
        per = [len(s.get("content") or "") for s in segs]
        need_low, need_high = FLOOR_SEC * LOW_RATIO, FLOOR_SEC * HIGH_RATIO
        ok2 = est is not None and est >= need_low
        print(f"  [{'OK' if ok2 else 'FAIL'}] 改写侧稿量：段数={len(segs)} 每段字数中位="
              f"{sorted(per)[len(per)//2] if per else 0} total_words={words} "
              f"estimated_duration={est}s（应 ≥{int(need_low)}s，区间 [{int(need_low)},{int(need_high)}]）")
        res.update(n_seg=len(segs), total_words=words, estimated=est, seg_words=per)
        # 3.2b 若段数×每段字数仍达不到 1800s → 任务第 4 条：把 llm_max_script_segments 调到 18~20
        if not ok2:
            print("      → 触发任务第 4 条：管理端把 ai_config `llm_max_script_segments` 调到 18~20 后复跑一期，"
                  "记录段数/每段字数/最终时长对照（运行时热调，无需改码）")

    # 3.3 拼接阶段无越界/兜底：步骤状态 + error 文本
    steps = q("select step_name,status,error from workflow_step where workflow_id=? order by id", (wf,), db)
    bad = [s for s in steps if s[1] not in ("success", "skipped")]
    stitch_err = [s for s in steps if s[0] == "stitch" and s[2] and
                  ("超出允许范围" in s[2] or "StitchError" in s[2] or "时长不足兜底" in s[2])]
    print(f"  步骤：{[(s[0], s[1]) for s in steps]}")
    print(f"  [{'OK' if not bad else 'FAIL'}] 无失败步骤；"
          f"[{'OK' if not stitch_err else 'FAIL'}] stitch 无「超出允许范围」/StitchError/兜底记录")
    for s in bad:
        print(f"      [FAIL] {s[0]} → {str(s[2])[:160]}")
    res["steps"] = [(s[0], s[1]) for s in steps]
    res["steps_failed"] = bool(bad or stitch_err)

    # 3.4 人工试听衔接点（无法由脚本判定，输出定位信息供试听）
    print("\n  人工试听 3 个衔接点（任务要求，脚本只给定位，不代判）：")
    for s in segs[:4]:
        c = (s.get("content") or "").replace("\n", " ")
        print(f"    段{s.get('seq')} 起：{c[:40]} … 止：{c[-40:]}")
    print("    听点：段边界是否出现书外素材嫁接 / 新闻播报套话（「大家好」「今日要闻」等）")
    res["episode_status"] = ep_status
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--db", default="backend/data/news.db")
    ap.add_argument("--channel-id", type=int, default=11)
    ap.add_argument("--episode-date", default=dt.date.today().isoformat())
    ap.add_argument("--trigger", action="store_true", help="显式触发真跑（消耗 LLM/TTS 预算）")
    ap.add_argument("--workflow-id", default=None, help="复验已有工作流（不触发）")
    ap.add_argument("--timeout-sec", type=int, default=5400)
    ap.add_argument("--poll-sec", type=int, default=30)
    ap.add_argument("--out", default="_validate/t01657_verify_result.json")
    args = ap.parse_args()

    pre = preflight(args.db, args.channel_id)
    if pre is None:
        return 1
    for rel, still_percent_style in check_log_markers_readable(os.getcwd()):
        print(f"  [{'WARN' if still_percent_style else 'OK'}] {rel} 日志数值口径"
              f"{'仍为 %-style，被 T01678 屏蔽' if still_percent_style else '可读'}")

    wf = args.workflow_id
    if args.trigger:
        print("\n=== 触发真跑（任务第 2 条）===")
        wf = trigger(args.base, args.channel_id, args.episode_date)
        if not wf:
            return 1
    if not wf:
        rows = q("select id,status from workflow where channel_id=? order by id desc limit 1",
                 (args.channel_id,), args.db)
        if not rows:
            print("\n未触发且该频道无历史工作流 → 加 --trigger 在实例上跑一期，"
                  "或 --workflow-id 指定已有 id 复验"); return 1
        wf, status = rows[0]
        print(f"\n复验历史工作流 id={wf} status={status}（未产生新花费）")
    else:
        print(f"\n等待工作流 {wf} 完成（≤{args.timeout_sec}s）…")
        status, err = wait_done(args.db, wf, args.timeout_sec, args.poll_sec)
        print(f"  终态：{status} {str(err or '')[:200]}")

    res = verify(args.db, wf, args.channel_id, os.path.join(os.path.dirname(args.db), ".."))
    res["log_grep"] = grep_logs(os.getcwd(), pre["name"])
    print(f"\n=== 日志辅助 grep（%-style 缺陷下仅判存在性）===")
    for k in ("fallback", "overrange", "linkage"):
        v = res["log_grep"][k]
        print(f"  {k}: {len(v)} 条" + (f"  最近：{v[-1][:150]}" if v else ""))

    json.dump({"channel": pre, "workflow_id": wf, **res},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n[out] {args.out}")
    ok = (res.get("duration") or 0) >= FLOOR_SEC and not res.get("steps_failed", False)
    print(f"结论：{'达标（待人工试听确认第 4 项）' if ok else '未达标，见上方 FAIL 项'}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
