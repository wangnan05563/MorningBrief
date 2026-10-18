来源：T02486（FR-UX-103 审计日志脱敏 / 令牌服务端化）

本单把数据库维护的三个危险接口改成「手输确认文本 + 服务端 `DB_ADMIN_CONFIRM_TOKEN` 作总开关」，
但同族的备份/恢复接口 `backend/app/routers/admin/backup.py` 仍是旧口径
（`_validate_confirm_token(body.confirm_token)` 等值比较前端传来的令牌）。
当前该令牌没有内置在前端产物里，**不构成泄露**，问题是同一套危险操作确认存在两个口径：
前端要传密钥的接口 = 迟早有人把密钥写进 bundle。

要做的事：
1. `backup.py` 改为 `_validate_danger_op(confirm_text, expected)`：恢复操作要求手输目标备份文件名
   （或文件名 + `RESTORE`），服务端配置只作总开关，不再向前端下发/要求令牌。
2. 前端备份恢复入口（若有）提示改为手输文件名；确认按钮在未输入时禁用。
3. 测试：未配置 `DB_ADMIN_CONFIRM_TOKEN` → 禁止；确认文本不匹配 → 报错且响应体不含服务端配置值。
4. 顺带核查全仓是否还有 `confirm_token` 形态的前端内置密钥（`grep -rn "confirm_token" apps/ backend/`），
   结果写进回传。

参考实现：`backend/app/routers/admin/db_admin.py` 的 `_validate_danger_op`（commit `eccd084`）。
