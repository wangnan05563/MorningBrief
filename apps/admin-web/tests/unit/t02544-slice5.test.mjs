/**
 * T02544 切片 5：数据安全组 G9 / M30 / M50
 *
 * 评审口径（T02336 §4.3）：
 * - G9 确认：webhook URL 的 access_token 等凭据参数必须脱敏（T02519/T02826 已闭环，本单只复核防线没退化）；
 * - M30 需修订：危险操作不许用「前端自动取用的一次性 nonce」当确认，改成手输表名，令牌只留在服务端
 *   （T02592/T02596 已闭环，本单只复核）；
 * - M50 需修订：CSV/JSON 两个 Tab 不得共用一份输入，且「单次最多导入 5000 行」既无后端校验也不该出现。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf-8')
const SRC = '../../src/'

const configPy = repoFile('backend/app/services/notification/config_service.py')
const dbAdminPy = repoFile('backend/app/routers/admin/db_admin.py')
const dangerOpPy = repoFile('backend/app/core/danger_op.py')
const dbAdminServicePy = repoFile('backend/app/services/db_admin_service.py')
const notificationVue = read(`${SRC}views/notification/NotificationConfig.vue`)
const dbAdminVue = read(`${SRC}views/maintenance/DatabaseAdmin.vue`)

test('G9 复核：webhook 的 access_token 在 GET 侧脱敏，脱敏值回传不覆盖真凭据', () => {
  assert.match(configPy, /_WEBHOOK_SECRET_PARAMS = \{[^}]*"access_token"/)
  assert.match(configPy, /def _mask_webhook\(/)
  // GET 响应两条 webhook 都必须走 URL 脱敏，而不是原样回显
  assert.match(configPy, /"dingtalk_webhook": _mask_webhook\(raw\["notify_dingtalk_webhook"\]\)/)
  assert.match(configPy, /"wecom_webhook": _mask_webhook\(raw\["notify_wecom_webhook"\]\)/)
  // 前端把脱敏值原样保存 = 未修改，不能拿 **** 覆盖真凭据
  assert.match(configPy, /_is_masked\(value\):\s*\n\s*return None/)
  // 界面提示与后端行为一致（审查时这句注释是空头承诺，现在是真的）
  assert.ok(notificationVue.includes('后端对 webhook 的凭据参数做「****尾4」脱敏'))
})

test('M30 复核：删除确认认手输表名，令牌只在服务端且不下发前端', () => {
  // 前端：必须逐字输入表名，按钮才可点
  assert.match(dbAdminVue, /deleteConfirmInput !== selectedTable/)
  assert.match(dbAdminVue, /请输入表名/)
  // 前端产物里不许再出现令牌/一次性 nonce 之类的「自动取用」凭据
  assert.doesNotMatch(dbAdminVue, /nonce/i)
  assert.doesNotMatch(dbAdminVue, /CONFIRM_TOKEN/)
  // 后端：确认文本与目标表名比对，总开关未配置即拒绝
  assert.match(dbAdminPy, /_validate_danger_op\(confirm_text, table\)/)
  assert.match(dbAdminPy, /_validate_danger_op\(body\.confirm_text, table\)/)
  assert.match(dangerOpPy, /if not server_token:/)
  assert.match(dangerOpPy, /hmac\.compare_digest/)
})

test('M50 CSV/JSON 各用各的输入框，切格式不串味', () => {
  assert.match(dbAdminVue, /v-model="importCsvContent"/)
  assert.match(dbAdminVue, /v-model="importJsonContent"/)
  assert.match(
    dbAdminVue,
    /const importContent = computed\(\(\) =>\s*importFormat\.value === 'json' \? importJsonContent\.value : importCsvContent\.value,?\s*\)/,
  )
  // 导入成功后两份输入都清空（计算属性不可写，必须显式清源）
  assert.match(dbAdminVue, /importCsvContent\.value = ''/)
  assert.match(dbAdminVue, /importJsonContent\.value = ''/)
})

test('M50 「5000 行」声明删除，CSV 解析交给后端标准库', () => {
  assert.doesNotMatch(dbAdminVue, /5000 行/)
  // 前端不再自己按逗号切 CSV（引号内逗号/换行会被切成垃圾行）
  assert.doesNotMatch(dbAdminVue, /split\(','\)/)
  assert.match(dbAdminServicePy, /csv\.DictReader\(io\.StringIO\(text_content, newline=""\)\)/)
})
