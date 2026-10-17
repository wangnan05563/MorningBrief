## 4.1 系统维护组跨菜单共性问题

本节由本切片内 7 个页面的证据归纳，均可由单点改动收敛：

1. **[高] 同级破坏性操作，确认强度相差两个量级**（R3 的最严重现场）：`DatabaseAdmin`/`VectorAdmin` 要求输入 `CONFIRM_DELETE`（`pages/Maintenance/DatabaseAdmin.tsx:394-404`、`pages/Maintenance/VectorAdmin.tsx:90-122`），`BatchRefresh` 的「清空全部」只有 `Popconfirm`（`pages/Maintenance/BatchRefresh.tsx:1067-1075`），`Cleanup` 的三个真实删除只用浏览器原生 `globalThis.confirm('确认清理缓存？此操作不可撤销。')`（`pages/Maintenance/Cleanup.tsx:88,116,143`），`Tunnel` 的「停止」零确认（`pages/Maintenance/Tunnel.tsx:596-605`）。建议抽 `dangerConfirm({ 范围, 命中条数, 是否可撤销 })` 一个组件，全组按「不可逆 + 影响他人」分级。成本：中（一次性收益覆盖全仓）。
2. **[高] `@cached_ttl(60)` 让"执行完立刻核对结果"变成不可能**：清理后前端马上 `loadStatus()`（`Cleanup.tsx:102,130,162`），但 `/api/maintenance/status` 带 60s 缓存（`web/routes/api_maintenance.py:70`）；向量库同因（`web/routes/api_vector_admin.py:138` vs `VectorAdmin.tsx:136,152,171,194`）。用户看到数字没变 → 判为失败 → **再点一次真实删除**。修法：写操作后由后端失效对应缓存 key，或前端刷新带 `force=1`。成本：低。
3. **[中] 审计回执跨页不互通**：`db_admin.*`（`api_db_admin.py:934`）、`maintenance.*`（`api_maintenance.py:438`）、客服向量库另写 `chatbot_audit_logs`（`api_vector_admin.py:56-61`）三套前缀/三张表，而两个审计抽屉的实现还相反——`DatabaseAdmin.tsx:573` 不 `await` 就打开（失败也显示"暂无数据"），`VectorAdmin.tsx:202-210` 先 `await` 才打开（慢数秒无反应）。建议合并为一个 `AuditLogDrawer` 组件 + 一个查询视图。成本：中。
4. **[中] 预览（dry-run）能力三种做法**：`Cleanup` 有开关且默认 true（`Cleanup.tsx:291-298`、`:42-55`）但预览成功时不发任何反馈（`:101-104`、`:129-132`），`DatabaseAdmin` 删除前强制级联预览（`:132-149`），`VectorAdmin` 的数据清理 Tab 完全没有预览（`:350-374`）；移动端反而比桌面端完整（`mobile/pages/Cleanup/index.tsx:79-82,109,128` 会区分「预览/立即执行」并给回执）。建议桌面端向移动端对齐。成本：低。
5. **[中] 页面无 `.page-container`，引导锚点整段失效**：`AntiCrawl/index.tsx:543` 与 `Maintenance/Tunnel.tsx:552` 用内联 `padding: 24`，而 `guides/menuGuides.ts:159-161,171-173` 已为这两页写好 Tour，容器缺失导致高亮定位失败（`guides/GuideController.tsx:94`）。成本：极低。
6. **[中] 服务器路径与实现术语直接呈给运营用户**：`VectorAdmin.tsx:269-271` 常驻展示 `persist_path`，`Tunnel.tsx:261,333` 把 `cert_file`/`credentials_file` 作为可复制主信息，`AntiCrawl/index.tsx:715-745` 直陈「UA / Profile / GPU / Stealth 脚本 / AWSC」。建议路径入 tooltip，术语换中文并配一句"该数字意味着什么"。成本：低。
7. **[低] 危险/告警语义色被复用为选中态**：`DatabaseAdmin.tsx:613-614` 用 `var(--xh-bg-warning)` + 3px `#FF6200` 表示"当前选中的表"，与本页删除按钮的危险色同形。成本：低。

**本组无「未发现显著体验缺陷」的页面**——7 个页面均有可指认缺陷；其中 `DatabaseAdmin` 的「级联预览 + 输入 token + 审计落库」三件套是全仓最成熟的安全设计，应作为其它维护页的对齐基线（而非反过来的问题页）。
