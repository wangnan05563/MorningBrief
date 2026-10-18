⚠ 阻塞：本环境无法真实最小化窗口或切后台标签，只能覆写 `document.hidden` 并手动派发 `visibilitychange`；「浏览器恢复前台后补发提示的实际时机与观感」需要真人验证；依赖：一台可最小化窗口的 Windows 机器 + 已构建的 admin-web

来源：T02495（FR-UX-301 可见性感知的反馈队列）

## 待验证内容

T02495 用 Playwright 覆写 `document.hidden` 的方式验证了入队/聚合/TTL/loading 不入队/确认框不回放这 5 条语义（`apps/admin-web/tests/feedback-queue.spec.js`，5 passed）。但**真实窗口最小化**下的两点未能自动化覆盖：

1. **补发时机观感**：真实最小化 → 恢复时，浏览器可能合并/延迟 `visibilitychange`，`_RESTORE_MS = 2000` 的抑制窗口与 `_flush()` 的落地时刻是否还会出现「刚点回来就弹一堆」或「等 2 秒才弹」的观感问题。
2. **最小化期间完全不插 DOM**：自动化只断言了 `.el-message` 插入计数为 0；真实最小化时若某个组件绕过 `src/utils/message.js` 直接 `import { ElMessage } from 'element-plus'`，仍可能唤起窗口。需要真机确认没有此类旁路。

## 人工验证步骤

1. `cd apps/admin-web && npm run build`，用生产构建（不是 dev server）打开审核页；
2. F12 → Network → 把某个接口 throttle 或直接改 mock 让它失败；
3. 最小化窗口，等待 ≥ 10 秒（期间制造 3–6 条错误提示，含重复文案）；
4. 恢复窗口：应只见 **1 条**聚合提示（最高等级 + 「共积压 N 条」后缀），且恢复瞬间无连锁弹窗、无窗口激活抖动；
5. `grep -rn "from 'element-plus'" apps/admin-web/src | grep -i "ElMessage"` 检查除 `src/utils/message.js` 外是否有绕过安全包装器的直接引用，有则改为从 `@/utils/message` 导入。

## 备注

任务保持待办可见（不归档），标 `【缺环境】` 前缀。真机验证通过后按 T02495 的证据格式回传并标 done。
