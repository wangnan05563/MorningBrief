# T02484 处理结果：FR-UX-101 敏感列禁止回写

## 根因

数据库维护页把列表接口下发的脱敏占位值（`***`）当作真实值整行回传，后端 `update_row` 又不校验列敏感性，直接 `SET password_hash = '***'`；同时 `ai_config.config_value` 按整列判定敏感，会把非密钥行一起封锁。

## 影响范围

- 后端行写入：`admin_user.password_hash`、`jwt_blacklist.token` 等 `SENSITIVE_COLUMNS`，以及 `ai_config` 密钥行的 `config_value`——保存一次即凭据不可恢复。
- 前端：数据库维护页新增/编辑弹窗（整行预填提交）。
- 不涉及其他模块，接口契约未变（PATCH 仍是脏字段语义）。

## 修复（绝对路径与改动点）

1. `D:\code\otherProjects\20_News\backend\app\services\db_admin_service.py`
   - 新增 `_MASK_SENTINEL_RE` / `_is_mask_sentinel()` 识别脱敏占位值；新增 `_row_sensitive_columns()` 按**整行数据**判断敏感列（`ai_config` 用该行 `config_key` 动态判定，不再按列一刀切）；新增 `_mask_writeback_message()` 统一提示。
   - `update_row()`：过滤后先做哨兵检查，命中抛 `BizError(code=400)`「敏感字段 … 传入的是脱敏占位值…请留空保持原值，或通过对应的专用配置入口修改」；`ai_config` 未提交 `config_key` 时先查当前行 `config_key` 再判定，避免改备注误判。
   - `create_row()`：同样拒绝把脱敏值当新凭据写入。
2. `D:\code\otherProjects\20_News\apps\admin-web\src\views\maintenance\DatabaseAdmin.vue`
   - 编辑弹窗改为**脏字段提交**：`openEditDialog` 保存 `originalForm` 快照，新增 `buildDirtyValues()` 只回传变化字段，跳过主键列、后端标记 `col.sensitive` 的列与形如 `***` 的值；无变化时提示「没有需要保存的修改」不发请求。
   - 敏感列在编辑态禁用输入，字段提示追加「敏感字段（编辑时只读，保持原值）」，schema 的 `sensitive` 标记由后端 `get_table_schema` 既有字段提供。
3. `D:\code\otherProjects\20_News\backend\tests\test_db_admin_sensitive_guard.py`（新增，5 例）
   - 覆盖 ACC-UX-101 验收 1/2：`password_hash` 传 `***` 被拒且原值不变；只改 `nickname` 时哈希逐字节一致；`ai_config` 密钥行拒绝脱敏值、非密钥行仍可正常写；新增行同样拦截。

## 验证（实测证据）

- `cd backend && .venv/Scripts/python.exe -m pytest tests/test_db_admin_sensitive_guard.py -q` → **5 passed in 1.24s**。
- 断言方式：拒绝路径检查 `BizError` 文案含「敏感字段」，写入路径用 `db_session.refresh()` 回读真实列值比对（非 mock）。
- 未做：前端交互未走浏览器实测（仅构建级验证待 M1 收尾统一跑），故本单标 done 不标 verified。

## 本次回写

- 无新增派生单。INT-01（敏感列哨兵接口，T02524）由本次后端拒绝逻辑与 `sensitive` schema 标记覆盖；FR-UX-103 的审计脱敏在同文件后续单处理。

## 下一步建议

- （仅观察不建单）真机验收 ACC-UX-101 第 1/2/5 条需在浏览器走一遍编辑弹窗，已包含在 REQ-020 全端 UI 实测抽查（T02549）范围内。
