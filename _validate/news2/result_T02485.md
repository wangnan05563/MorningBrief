# T02485 处理结果：FR-UX-102 导入 replace 不销毁未提交列

## 根因

`import_rows` 的 replace 模式用 `INSERT OR REPLACE`：SQLite 语义是**先删后插**，只带部分列时会把未提供的列（含 `password_hash` 等凭据）重置为默认值/NULL。同时 CSV 在前端用 `split(',')`/`split('\n')` 手拆，引号内逗号、CRLF、BOM 都会解析成垃圾行；导入前也没有任何 dry-run，用户只能在写完后发现错了。

## 影响范围

- 数据库维护页「导入数据」全部白名单表（15 张），replace 模式一次即可静默清空凭据列。
- 接口：`POST /admin/api/v1/db-admin/tables/{table}/import`（新增可选 `content`/`format`）与新增 `POST .../import/preview`。
- 前端：`DatabaseAdmin.vue` 导入弹窗、`api/dbAdmin.js` 的 `importRows` 调用形态（改为提交原始文本，由后端解析）。
- 不影响行级 CRUD（FR-UX-101 已单独处理）。

## 修复（绝对路径与改动点）

1. `D:\code\otherProjects\20_News\backend\app\services\db_admin_service.py`
   - `import_rows()`：replace 改为「存在即 `UPDATE` 显式列，不存在才 `INSERT`」，新增 `updated` 计数与「replace 缺少主键列」「仅含主键列无可更新字段」错误项；每行复用 FR-UX-101 的 `_row_sensitive_columns` + `_is_mask_sentinel` 拒绝脱敏占位值入库。
   - **未按 PRD 字面用 `ON CONFLICT DO UPDATE`**：实测 SQLite 对 upsert 仍按插入行校验 NOT NULL，只带 `id,nickname` 的 replace 会直接 `IntegrityError`（测试已捕获），因此冲突分支走纯 UPDATE，语义等价且能保住未提交列——PRD 口径需按此修订。
   - `parse_import_payload()`：CSV 用标准 `csv.DictReader`（`newline=""`，引号内逗号/换行、CRLF 正确），显式剥离 BOM，跳过全空行；JSON 要求数组。
   - `preview_import()`：只读 dry-run，返回 `to_insert / to_update / conflicts / error_rows / errors[:50] / primary_key / columns`。
   - `_pk_exists()`：主键存在性判定辅助。
2. `D:\code\otherProjects\20_News\backend\app\routers\admin\db_admin.py`
   - 新增 `POST /tables/{table}/import/preview`（`ImportPreviewRequest`）；`import` 端点支持 `content`+`format`，`rows` 变为可选（兼容既有调用）。
3. `D:\code\otherProjects\20_News\apps\admin-web\src\api\dbAdmin.js`
   - `importRows(table, content, format, mode)` 改为提交原始文本；新增 `previewImport()`。
4. `D:\code\otherProjects\20_News\apps\admin-web\src\views\maintenance\DatabaseAdmin.vue`
   - 删除前端手拆 CSV；导入弹窗新增「预览」按钮与预览面板（总行数/预计新增/更新/冲突/错误 + 前 10 条错误明细）；内容、格式、模式变化即失效预览；**未预览不允许确认导入**；replace 选项文案改为「仅更新本次提供的列，其余保持原值」；结果提示区分新增/更新/跳过。
5. `D:\code\otherProjects\20_News\backend\tests\test_db_admin_import_upsert.py`（新增 8 例）

## 验证（实测证据）

- `backend/.venv/Scripts/python.exe -m pytest tests/test_db_admin_import_upsert.py tests/test_db_admin_sensitive_guard.py -q` → **13 passed**。关键断言：
  - replace 只带 `id,nickname` → `updated=1`，`password_hash`/`username` 逐字节保持原值（ACC-UX-101 验收 3）。
  - 导入内容含 `***` → 行被拒并给出敏感字段提示。
  - `parse_import_payload('\ufeffid,nickname,remark\n901,"张,三","line1\r\nline2"\n')` → 单行三列，逗号与换行不串列。
  - `preview_import` 计算 1 更新 / 1 新增 / 1 冲突，且预览后目标行未写入库。
  - 预览接口经 TestClient + admin token 返回 200 且 data 计数正确。
- 前端构建：`apps/admin-web` `npm run build` → `✓ built in 22.20s`，`dist/assets/DatabaseAdmin-*.js` 16.56 kB 产物更新。
- 未做：浏览器交互实测（预览按钮点击链路），按 REQ-020（T02549）覆盖，故本单 done 不标 verified。

## 本次回写

- 无新增派生单：INT-UX-02（导入 dry-run，T02525）由本次 `import/preview` 端点与前端预览面板交付。
- 需修订 PRD 口径：FR-UX-102 的「改 `ON CONFLICT DO UPDATE`」应记为「冲突时只更新显式提供列（UPDATE 分支）」，原因见上（SQLite 对 upsert 仍校验插入行 NOT NULL）。已在评审报告 §5-R3 同源，属文字口径修正，不改变实施范围（仅观察，随 FR-UX-102 验收记录，不另建单）。

## 下一步建议

- （仅观察不建单）M1 收尾按 ACC-UX-001 跑一次编辑/导入/审计回归，由 T02531「M1 实施与验收」承载。
