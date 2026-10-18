# T02486 · [PRD] 1.3 FR-UX-103 审计日志脱敏

> 需求：敏感列脱敏；令牌服务端校验（PRD `docs/需求规格说明书-UX优化.md:87`，来源建议 M29）

## 根因

1. **确认令牌被打包进前端产物**。`apps/admin-web/src/api/dbAdmin.js` 里硬编码了
   `export const CONFIRM_TOKEN = 'CONFIRM_DELETE'`，删除/批量删除/导入三个接口都直接把它当参数发出。
   后端 `_validate_confirm_token` 又拿这个值与 `settings.DB_ADMIN_CONFIRM_TOKEN` 做等值比较，
   等于「开关的钥匙写死在浏览器里」——任何人打开管理端打包产物（或 F12 看一眼模块）即可执行危险操作，
   二次确认形同不存在。
2. **审计明细按原文落库**。`DbAdminService.write_audit` 直接 `json.dumps(detail)`，
   而 create/update/import 的 `detail` 就是用户提交的整包 `values`。
   于是管理员改一次密码、填一次 `ai_config` 的 API Key，明文密钥就永久留在 `audit_log.detail` 里；
   审计日志页（`/audit-log`）还把 `detail` 原样下发给前端展示，形成第二条泄露路径。
3. **敏感判定口径重复了三份**：`_mask_sensitive`（列表读取）、写回守卫、审计脱敏各写各的，
   PRD 技术要点要求的「与服务端读取口径共用」当时并不成立。

## 影响范围

- `backend/app/services/db_admin_service.py`：新增 `_mask_audit_detail()`；`write_audit` 写入前脱敏；
  `list_audit_logs` 读取后再脱敏一次（覆盖修复前落库的历史明文行）；`_mask_sensitive` 重构为复用
  `_row_sensitive_columns`，列表/编辑/schema 标记/写回守卫/审计现在是同一套判定。
- `backend/app/routers/admin/db_admin.py`：`_validate_confirm_token` → `_validate_danger_op(confirm_text, expected)`；
  `DELETE /rows/{pk}`、`POST /rows/batch-delete`、`POST /import` 的入参从 `confirm_token` 改为 `confirm_text`。
- `apps/admin-web/src/api/dbAdmin.js`：删除内置令牌常量，三个危险接口改为传「确认文本」。
- `apps/admin-web/src/views/maintenance/DatabaseAdmin.vue`：删除确认框提示/占位符/按钮禁用条件改为「输入目标表名」。
- `apps/admin-web/src/views/help/Help.vue`：数据库维护功能说明文案同步（原文还在写「CONFIRM_DELETE 令牌」）。
- 兼容：`confirm_token` 参数已移除，仍按旧契约调用的外部脚本会收到 422「缺少 confirm_text」——
  全仓 grep 确认仅管理端调用，小程序/Electron 不涉及。备份恢复接口 `backup.py` 仍是 `confirm_token`，
  但该令牌只存在于后端（前端没有内置），本轮不动，见「下一步建议」。

## 修复

| 文件（绝对路径） | 改动点 |
| --- | --- |
| `D:\code\otherProjects\20_News\backend\app\services\db_admin_service.py` | 新增 `_SECRET_KEY_RE`（password/passwd/secret/token/api_key/access_key/private_key）与递归 `_mask_audit_detail(detail, table)`：按列名语义 + `_row_sensitive_columns` 行级判定打码为 `***`；`ai_config` 的字典里只有 `config_value` 而没有 `config_key` 时按 fail-safe 一律打码（update 只提交被改列时拿不到 key 语义）。`write_audit` 改为 `json.dumps(_mask_audit_detail(detail, target))`；`list_audit_logs` 反序列化后再脱敏一次；`_mask_sensitive` 改为复用 `_row_sensitive_columns` |
| `D:\code\otherProjects\20_News\backend\app\routers\admin\db_admin.py` | `_validate_danger_op(confirm_text, expected)`：`CONFIRM_TOKEN` 为空 → 直接禁止危险操作（总开关不再下发）；非空 → 校验调用者手输的确认文本（删除/批量删除须等于表名、导入须等于 `IMPORT`），用 `hmac.compare_digest` 常量时间比较，错误提示只说「请输入 X」不透出服务端配置值。`BatchDeleteRequest.confirm_text`、`ImportRequest.confirm_text="IMPORT"`、`delete_row` 的 `confirm_text` Query |
| `D:\code\otherProjects\20_News\apps\admin-web\src\api\dbAdmin.js` | 移除 `export const CONFIRM_TOKEN`；`deleteRow(table, pk, confirmText)`、`batchDelete(table, ids, confirmText)`、`importRows(...)` 固定传 `confirm_text: 'IMPORT'`（这是确认词不是密钥） |
| `D:\code\otherProjects\20_News\apps\admin-web\src\views\maintenance\DatabaseAdmin.vue` | 确认提示改为「请输入表名 {{ selectedTable }}」，`:disabled="deleteConfirmInput !== selectedTable"`（原写死 `!== 'CONFIRM_DELETE'`，若不一起改会让删除按钮永久禁用），`confirmDelete()` 先本地校验再提交并在成功后清空输入；批量删除与单行删除走同一个框，自动继承 |
| `D:\code\otherProjects\20_News\apps\admin-web\src\views\help\Help.vue` | 文案与新行为对齐（手输表名 / IMPORT，密钥不再进前端产物） |
| `D:\code\otherProjects\20_News\backend\tests\test_db_admin_audit_mask.py` | 新增 8 条测试 |

commit：`eccd084`（脱敏 + 确认文本改造 + 测试）、`5d0f03c`（`_mask_sensitive` 复用行级判定 + 回归测试）。

## 验证

命令层全链闭环（pytest + 构建 + 产物 grep），未做 UI 实测：

```
$ cd backend && .venv/Scripts/python.exe -m pytest tests/test_db_admin_audit_mask.py \
    tests/test_db_admin_sensitive_guard.py tests/test_db_admin_import_upsert.py -q
22 passed, 2 warnings in 3.31s
```

新增 `test_db_admin_audit_mask.py` 逐条断言：

- `_mask_audit_detail` 覆盖列名语义（`values.password_hash`、嵌套 `notify.access_token`）→ `***`，
  且 `SECRET not in json.dumps(masked)`；非敏感列 `username` 原样保留。
- `ai_config` 行级判定：`config_key=openai_api_key` 的 `config_value` 打码，`default_model` 的不打码。
- fail-safe：`detail` 只有 `config_value` 无 `config_key` 时打码；导入明细里的 `rows[].api_key` 打码。
- `write_audit` 落库后读 `AuditLog.detail` → 明文密钥不存在，`values.password_hash == "***"`。
- 完整链路：`svc.update_row("admin_user", ...)` 改了真实密钥 + `write_audit` 后，
  库中该表全部审计行均查不到明文。
- 历史明文行：手工 INSERT 一条未脱敏的 `audit_log`，`list_audit_logs()` 返回结果里
  明文密钥消失、`password_hash` 变为 `***`（证明读侧二次脱敏对旧数据生效）。
- `_mask_sensitive` 重构后列表口径不变（`admin_user.password_hash`、`ai_config` 敏感 key 打码，非敏感 key 保留）。
- 危险操作：`monkeypatch` 把 `CONFIRM_TOKEN` 置空 → 报「服务器未配置 DB_ADMIN_CONFIRM_TOKEN，危险操作被禁止」；
  配为 `server-side-only-secret` 后传错确认文本 → 报「确认文本不匹配」，且响应体不含服务端密钥。

前端构建与产物取证：

```
$ cd apps/admin-web && npm run build
✓ built in 19.98s
$ grep -rl "CONFIRM_DELETE" dist/     # 无输出 → 确认令牌已不在浏览器产物中
```

**验证缺口（如实标注）**：删除确认框的交互（必须手输表名才能点亮按钮）属 GUI 行为，本轮只做静态验证 +
构建通过，未做 UI 实测。人工抽查步骤：管理端 → 系统维护 → 数据库维护 → 选 `admin_user` → 勾选一行点删除，
1) 提示与占位符应显示当前表名而非 `CONFIRM_DELETE`；2) 不输入时「确认删除」置灰，输入表名后可点；
3) 输入错误表名提交返回「确认文本不匹配，请输入 admin_user」；4) 编辑一行 `password_hash` 保存后，
切到审计日志页看该条 detail 应为 `***`。

## 本次回写

- 无新增待审核派生单标题落在本单之外；本轮剩余工作已按「下一步建议」建 2 张派生子单
  （T02591 历史审计明文清洗、T02592 备份恢复接口确认口径统一）。
- 本单代码改动已通过 2 个 commit 落库：`eccd084`、`5d0f03c`；本文档随 `docs(validate)` commit 留痕。
- PRD `FR-UX-103` 技术要点原文要求「`detail.values` 对敏感列做脱敏（与服务端读取口径共用 `_mask_sensitive`）」，
  实现口径说明：脱敏判定共用 `_row_sensitive_columns`（`_mask_sensitive` 已改为调用它），
  但审计侧用新的递归 `_mask_audit_detail` 而非直接调用 `_mask_sensitive`——后者只能处理平铺行字典且就地改写，
  审计 `detail` 是 `{pk, values}` / `{mode, result:{rows:[...]}}` 的嵌套结构。

## 下一步建议

1. `audit_log` 表修复前落库的历史明文行仍留在库里（读侧已打码，但直接查库/导库仍能看到）——
   需要一次性清洗（把命中 `_SECRET_KEY_RE` 的 detail 值改写为 `***`）并纳入备份导出前的处理。
   **已建派生单 T02591**（清洗脚本 + 干跑预览 + 备份导出联动）。
2. 备份恢复接口 `backend/app/routers/admin/db_admin.py` 同族的 `routers/admin/backup.py` 仍是
   `confirm_token` 等值校验口径，与本轮 `_validate_danger_op` 不一致；当前令牌未下发前端、无泄露面，
   但同一套「危险操作确认」应只有一个口径。**已建派生单 T02592**（统一为确认文本 + 手输备份文件名）。
