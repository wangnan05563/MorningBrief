#!/usr/bin/env bash
# =============================================================================
# 业务范围扩展 MVP —— 课程频道端到端一键验证脚本
# -----------------------------------------------------------------------------
# 覆盖链路：配置课程频道(outline 选题 + 关广告)
#           → 上传文档(逐章入库)
#           → 手动触发(skip_crawl，从 rewrite 起)
#           → 轮询工作流至终态(success)
#           → 断言节目发布成功
#
# 前置条件（部署后手动准备）：
#   1) 后端已按单 worker 启动：uvicorn app.main:app --workers 1 --host 0.0.0.0 --port 8000
#   2) 服务端 .env 已配置真实 LLM / TTS 凭证，且 ffmpeg 可用
#   3) 已存在可用 B 端管理员账号（ADMIN_USER / ADMIN_PASS）
#
# 用法：
#   PYTHON=python3 BASE_URL=http://127.0.0.1:8000 \
#     ADMIN_USER=admin ADMIN_PASS='******' \
#     DOC_PATH=/path/to/doc.md \
#     [CHANNEL_ID=123] \
#     bash scripts/e2e_course_channel.sh
#
# 说明：
#   - 不传 CHANNEL_ID 时，脚本会新建一个临时课程频道（名称含 E2E_前缀），
#     并打印其 ID，便于事后在 admin 手动删除。
#   - 传 CHANNEL_ID 时，脚本会 PUT 覆盖为课程配置（selection_strategy=outline, enable_ad=0）。
#   - 去重口径：list 为全局 content_hash（与频道无关），同一文档重复上传会 409。
# =============================================================================

set -u
PYTHON="${PYTHON:-python}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_USER="${ADMIN_USER:-}"
ADMIN_PASS="${ADMIN_PASS:-}"
DOC_PATH="${DOC_PATH:-}"
CHANNEL_ID="${CHANNEL_ID:-}"
EPISODE_DATE="${EPISODE_DATE:-$( "$PYTHON" -c 'import datetime;print(datetime.date.today().isoformat())' )}"

# 课程频道配置（outline 选题 + 关广告 + 课程口吻模板）
SEL_STRATEGY="outline"
ENABLE_AD=0
REWRITE_TEMPLATE="rewrite_course.txt"
INTRO_PROMPT="同学你好，欢迎来到本节课程。今天我们要一起学习的内容，我会用最通俗的方式讲给你听，跟着节奏来，慢慢就能听懂。"
OUTRO_PROMPT="本节内容就到这里。建议你听完后结合原文再回顾一遍，把关键概念和例子在脑海里过一遍，理解会更扎实。我们下节继续。"

PASS=0; FAIL=0
TOKEN=""

step() { printf "\n=== %s ===\n" "$1"; }
ok()   { PASS=$((PASS+1)); printf "  [OK]   %s\n" "$1"; }
bad()  { FAIL=$((FAIL+1)); printf "  [FAIL] %s\n" "$1"; }

# 取 JSON 字段：json_get "$BODY" "data.token"
json_get() {
  "$PYTHON" - "$1" "$2" <<'PY'
import sys, json
body, path = sys.argv[1], sys.argv[2]
try:
    obj = json.loads(body)
except Exception as e:
    print(""); sys.exit(0)
node = obj
for part in path.split("."):
    if isinstance(node, dict) and part in node:
        node = node[part]
    else:
        print(""); sys.exit(0)
print(node if isinstance(node, str) else json.dumps(node, ensure_ascii=False))
PY
}

# 通用 API 调用：api METHOD PATH [BODY_OR_EMPTY]
# 自动带 Bearer；打印响应体到 stdout；HTTP 码写入 API_CODE
api() {
  local method="$1" path="$2" body="$3"
  local hdr=(-H "Authorization: Bearer ${TOKEN}")
  local -a args=(-sS -o /tmp/e2e_body.txt -w "%{http_code}")
  args+=(-H "Content-Type: application/json")
  args+=("${hdr[@]}")
  if [ "$method" = "POST" ] || [ "$method" = "PUT" ]; then
    args+=(-X "$method" --data "$body")
  else
    args+=(-X "$method")
  fi
  API_CODE=$(curl "${args[@]}" "${BASE_URL}${path}")
  API_BODY=$(cat /tmp/e2e_body.txt)
}

[ -z "$ADMIN_USER" ] && { echo "缺少 ADMIN_USER"; exit 2; }
[ -z "$ADMIN_PASS" ] && { echo "缺少 ADMIN_PASS"; exit 2; }
[ -z "$DOC_PATH" ] && { echo "缺少 DOC_PATH（待上传文档路径）"; exit 2; }
[ -f "$DOC_PATH" ] || { echo "DOC_PATH 不存在: $DOC_PATH"; exit 2; }

# ---------------------------------------------------------------- 1. 健康检查
step "1. 健康检查 ${BASE_URL}/api/health"
HEALTH=$(curl -sS -o /tmp/e2e_health.txt -w "%{http_code}" "${BASE_URL}/api/health")
if [ "$HEALTH" = "200" ]; then ok "服务可达 (HTTP 200)"; else bad "服务不可达 (HTTP $HEALTH)"; cat /tmp/e2e_health.txt; exit 3; fi

# ---------------------------------------------------------------- 2. 登录
step "2. 管理员登录 ${BASE_URL}/admin/api/v1/auth/login"
api POST "/admin/api/v1/auth/login" "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}"
if [ "$API_CODE" != "200" ]; then bad "登录失败 (HTTP $API_CODE)"; echo "$API_BODY"; exit 4; fi
TOKEN=$(json_get "$API_BODY" "data.token")
if [ -z "$TOKEN" ]; then bad "登录响应未含 data.token"; echo "$API_BODY"; exit 4; fi
ok "已获取 Bearer token"

# ---------------------------------------------------------------- 3. 课程频道
step "3. 课程频道配置 (selection_strategy=$SEL_STRATEGY, enable_ad=$ENABLE_AD)"
if [ -z "$CHANNEL_ID" ]; then
  CH_NAME="E2E_课程频道_$( "$PYTHON" -c 'import time;print(int(time.time()))' )"
  BODY=$(cat <<JSON
{"name":"${CH_NAME}","description":"e2e 临时课程频道","selection_strategy":"${SEL_STRATEGY}","enable_ad":${ENABLE_AD},"rewrite_template":"${REWRITE_TEMPLATE}","intro_prompt":"${INTRO_PROMPT}","outro_prompt":"${OUTRO_PROMPT}"}
JSON
)
  api POST "/admin/api/v1/channels" "$BODY"
  if [ "$API_CODE" != "200" ]; then bad "创建频道失败 (HTTP $API_CODE)"; echo "$API_BODY"; exit 5; fi
  CHANNEL_ID=$(json_get "$API_BODY" "data.id")
  ok "已创建课程频道 id=$CHANNEL_ID (名称=$CH_NAME)"
  AUTO_CREATED=1
else
  BODY=$(cat <<JSON
{"selection_strategy":"${SEL_STRATEGY}","enable_ad":${ENABLE_AD},"rewrite_template":"${REWRITE_TEMPLATE}","intro_prompt":"${INTRO_PROMPT}","outro_prompt":"${OUTRO_PROMPT}"}
JSON
)
  api PUT "/admin/api/v1/channels/${CHANNEL_ID}" "$BODY"
  if [ "$API_CODE" != "200" ]; then bad "更新频道失败 (HTTP $API_CODE)"; echo "$API_BODY"; exit 5; fi
  ok "已更新课程频道 id=$CHANNEL_ID"
fi

# 回读校验三字段已落库
api GET "/admin/api/v1/channels/${CHANNEL_ID}"
GOT_STRATEGY=$(json_get "$API_BODY" "data.selection_strategy")
GOT_AD=$(json_get "$API_BODY" "data.enable_ad")
if [ "$GOT_STRATEGY" = "$SEL_STRATEGY" ] && [ "$GOT_AD" = "$ENABLE_AD" ]; then
  ok "回读确认 selection_strategy=$GOT_STRATEGY enable_ad=$GOT_AD"
else
  bad "回读不一致：strategy=$GOT_STRATEGY ad=$GOT_AD（期望 $SEL_STRATEGY/$ENABLE_AD）"
fi

# ---------------------------------------------------------------- 4. 上传文档
step "4. 上传文档 → 逐章入库 (channel_id=$CHANNEL_ID)"
# 上传为 multipart/form-data，单独用 curl 传文件
API_CODE=$(curl -sS -o /tmp/e2e_body.txt -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "file=@${DOC_PATH}" \
  -F "channel_id=${CHANNEL_ID}" \
  -F "source=文档上传" \
  "${BASE_URL}/admin/api/v1/materials/upload")
API_BODY=$(cat /tmp/e2e_body.txt)
if [ "$API_CODE" != "200" ]; then
  bad "上传失败 (HTTP $API_CODE)"; echo "$API_BODY"; exit 6
fi
UP_COUNT=$(json_get "$API_BODY" "data.count")
ok "上传成功，入库素材数=${UP_COUNT:-?} (HTTP 200)"

# ---------------------------------------------------------------- 5. 触发
step "5. 手动触发 (skip_crawl=true, episode_date=$EPISODE_DATE)"
TRIG_BODY="{\"channel_id\":${CHANNEL_ID},\"skip_crawl\":true,\"episode_date\":\"${EPISODE_DATE}\"}"
api POST "/admin/api/v1/workflows/trigger" "$TRIG_BODY"
if [ "$API_CODE" != "200" ]; then bad "触发失败 (HTTP $API_CODE)"; echo "$API_BODY"; exit 7; fi
WF_ID=$(json_get "$API_BODY" "data.workflow_id")
if [ -z "$WF_ID" ]; then bad "触发响应未含 workflow_id"; echo "$API_BODY"; exit 7; fi
ok "已触发工作流 workflow_id=$WF_ID"

# ---------------------------------------------------------------- 6. 轮询
step "6. 轮询工作流状态（最多 600s）"
WSTATUS=""
for i in $(seq 1 60); do
  sleep 10
  api GET "/admin/api/v1/workflows/${WF_ID}"
  WSTATUS=$(json_get "$API_BODY" "data.status")
  printf "  ... 第 %ds 状态=%s\n" "$((i*10))" "$WSTATUS"
  if [ "$WSTATUS" = "success" ] || [ "$WSTATUS" = "failed" ]; then break; fi
done
if [ "$WSTATUS" = "success" ]; then ok "工作流成功（rewrite→tts→stitch→publish 全链路通过）";
elif [ "$WSTATUS" = "failed" ]; then bad "工作流失败"; echo "$API_BODY";
else bad "轮询超时，最后状态=$WSTATUS"; fi

# ---------------------------------------------------------------- 7. 节目断言
step "7. 节目发布断言"
api GET "/admin/api/v1/workflows?channel_id=${CHANNEL_ID}&episode_date=${EPISODE_DATE}&status=success"
EP=$(json_get "$API_BODY" "data.list")
if [ -n "$EP" ] && [ "$EP" != "[]" ]; then ok "查询到成功节目（频道=$CHANNEL_ID 日期=$EPISODE_DATE）";
else bad "未查询到成功节目"; echo "$API_BODY"; fi

# ---------------------------------------------------------------- 汇总
printf "\n==================== 结果: %d 通过 / %d 失败 ====================\n" "$PASS" "$FAIL"
if [ "$WSTATUS" = "success" ]; then
  echo "结论：课程频道端到端闭环通过（outline 选题 + enable_ad=0 关广告 + 课程模板 rewrite + 发布）。"
  echo "后续人工核查：播放 episode 音频，确认章节顺序与文档一致、无广告段。"
  [ -n "${AUTO_CREATED:-}" ] && echo "（本次新建的临时频道 id=$CHANNEL_ID 可在 admin 手动删除）"
fi
exit $((FAIL>0?1:0))
