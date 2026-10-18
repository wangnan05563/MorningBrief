来源：T02486（FR-UX-103 审计日志脱敏）

`write_audit` 自本单起写入前脱敏、`list_audit_logs` 读取后再脱敏，但**修复前落库的历史 `audit_log.detail` 仍是明文**（密码哈希、AI Key、通知 token 等）。审计日志页看不到，直接查库/导库/备份文件仍能看到。

要做的事：
1. 写一次性清洗脚本（放 `backend/scripts/`）：扫描 `category='db_admin'` 的 `detail`，用与 `_mask_audit_detail` 同一套判定（`_SECRET_KEY_RE` + `_row_sensitive_columns`）把命中值改写为 `***`；先支持 `--dry-run` 输出将改动的行数与样本，再执行。
2. 清洗前后行数/非命中字段不变的断言测试（in-memory SQLite 造历史明文行）。
3. 与备份导出联动：确认 `backup` 导出的 SQL/CSV 里 `audit_log` 不再含明文密钥（若导出走原库，则清洗必须先行，或在导出路径同样调用脱敏）。
4. 回写：清洗脚本路径、dry-run 计数、执行计数、导出取证。

约束：不得改用户生产库前先干跑；清洗只在明确批准后执行。
