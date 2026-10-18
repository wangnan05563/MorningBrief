# T02493 交付结果 —— 2.5 FR-UX-205 上传可回退

需求口径（PRD FR-UX-205，覆盖条目 H9 / J60）：同名文件先检测并确认；删除/清空展示影响条数；
提供最近删除/回收站或至少操作前快照提示。

## 根因

1. **覆盖只靠前端拦，后端一律静默覆盖**：`CosStorageService.upload_file` 直接
   `put_object`，任何「同名 key」的写入都会把旧对象换掉。前端 `handleFileSelected` 原本
   的做法是「先拉一次目录列表 → 在列表里找同名 → 弹确认」，存在两个洞：
   - 列表是进入目录时的快照，可能已过期（TOCTOU）；
   - 直接调 `POST /cos/upload`（脚本、误用、别的入口）完全绕过确认。
2. **确认框实际上从未弹出（真实缺陷，E2E 才发现）**：`CosFiles.vue` 里调用了
   `dangerConfirm(...)`，但**没有 import**（`git grep` 确认全仓只有这一处漏导入）。
   运行时抛 `ReferenceError: dangerConfirm is not defined`，被全局 Promise 守卫
   （`[global] 未处理的 Promise 拒绝（已捕获…）`）吞掉，界面表现为「选了文件后毫无反应」，
   于是同名上传实际上仍是直接 `uploadCosFile` → 静默覆盖。控制台留痕（实测）：
   ```
   CONSOLE: warning [Vue warn]: Unhandled error during execution of native event handler
   CONSOLE: warning [global] 未处理的 Promise 拒绝（已捕获，避免控制台报错）: ReferenceError: dangerConfirm is not defined
   ```
3. **即便弹了确认，也没有任何回退手段**：文案只能写「由 COS 版本策略决定是否能找回」，
   对没开版本控制的桶等于「覆盖即丢」。
4. J60（小程序下载页三档删除权重一致、无条数）已由 **T02490 / FR-UX-202** 落地，本单不重复实现。

## 影响范围

- 云端存储 > 文件管理 的上传链路（唯一 `/cos/upload` 调用方，`git grep uploadCosFile` 确认）。
- 所有「重传同名音频/素材」的运维动作：行为从「静默覆盖」变为「先拒绝、确认后带快照覆盖」。
- 桶内新增 `.backup/` 目录（快照落盘位置，按对象所在目录就近存放）。
- 未改动：`/cos/move`（重命名/移动）仍是旧的静默覆盖行为 —— 已建派生单 T02608；
  快照的恢复入口与保留策略本环境未做 —— 已建派生单 T02609。

## 修复（文件绝对路径与改动点）

1. `D:\code\otherProjects\20_News\backend\app\services\cos_storage_service.py`
   - 新增 `object_exists(key)`：`object_exists` + `head_object` 组合，返回
     `{key, exists, size, last_modified, content_type}`；不存在时 `exists=False` 而非报错。
   - `upload_file(..., overwrite: bool = False)`：
     - 同名且 `overwrite=False` → `BizError(code=409)`（HTTP 200 + 统一信封），message 点名
       key、可读大小与更新时间，并说明「已拒绝覆盖上传，请确认后再以覆盖方式重传」；
     - 同名且 `overwrite=True` → 先 `_snapshot_before_overwrite(key)` 再 `put_object`；
     - 返回值补 `overwritten / previous / backup_key`。
   - 新增 `_snapshot_before_overwrite(key)`：复制旧对象到 `<同目录>/.backup/<%Y%m%d-%H%M%S>/<文件名>`；
     备份槽位被占用则追加 `-1/-2`，**备份失败即中止覆盖**（消息「覆盖前快照备份失败，已中止覆盖：…」）；
     探测上限 `_MAX_BACKUP_PROBES = 20`（超出直接拒绝，杜绝无限循环）。
   - 新增 `_human_size(size)`（`None → 大小未知`，其余 B/KB/MB/GB）。
2. `D:\code\otherProjects\20_News\backend\app\routers\admin\cos.py`
   - `POST /cos/upload` 增加 `overwrite: bool = Form(False)`；覆盖成功时 message 带上备份 key
     （「已覆盖上传，旧文件已备份至 …」）。
   - 新增 `GET /cos/exists?key=`（同名检测，管理员权限）。
3. `D:\code\otherProjects\20_News\apps\admin-web\src\api\cos.js`
   - `uploadCosFile(file, prefix, { overwrite })` 显式携带 `overwrite` 字段（默认 false）；
   - 新增 `checkCosObject(key)`，带 `silent: true`（检测失败由调用方给针对性提示，避免拦截器二次弹错）。
4. `D:\code\otherProjects\20_News\apps\admin-web\src\views\cos\CosFiles.vue`
   - **补上漏掉的 `import { dangerConfirm } from '../../utils/dangerConfirm'`**（本单真实缺陷修复）；
   - `handleFileSelected` 改为：服务端 `checkCosObject` 权威检测 → 同名走 `dangerConfirm`
     （动作 + 对象 + 旧对象大小/更新时间 + 「覆盖前自动备份到 `.backup/<时间戳>/`」+ 确认词「覆盖」）；
     检测失败**中止上传**并说明原因（不盲传）；上传带 `overwrite: exists`；
     成功提示点名快照位置；服务端 409 时不再显示成功提示。
5. 测试
   - 新增 `D:\code\otherProjects\20_News\backend\tests\test_t02493_cos_overwrite_guard.py`（16 条）；
   - 新增 `D:\code\otherProjects\20_News\apps\admin-web\tests\cos-upload-rollback.spec.js`（5 条 E2E）；
   - `test_cos_storage_service.py` / `test_cos_router.py` 的既有上传用例补 `object_exists` 桩
     （改动 4 行，不改断言意图）。

## 验证（实测证据）

- 后端：`backend/.venv/Scripts/python.exe -m pytest tests/test_t02493_cos_overwrite_guard.py
  tests/test_cos_storage_service.py tests/test_cos_router.py tests/test_cos_c_presign.py -q`
  → **55 passed** in 34.77s（含新 16 条：拒绝静默覆盖 / 覆盖先备份 / 桶根路径 / 备份不覆盖既有快照
  （时钟固定为 `20261018-160000`，断言 `-1` 后缀）/ 备份失败中止 / 全新对象不备份不查元数据 /
  存在性检查两种口径 / 未配置守卫 / 路径穿越 / `_human_size` / 路由 409 与 `overwrite=true` 贯通 /
  `/cos/exists` 信封与 401 / 探测上限防死循环）。
- 前端构建：`npm run build` → **✓ built in 41.25s**。
- E2E（Playwright + 本机 Chrome，mock `/cos/*`）：
  `npx playwright test cos-upload-rollback.spec.js destructive-confirm.spec.js auto-review-guard.spec.js`
  → **17 passed** in 1.1m。新 5 条断言：
  ① 同名上传弹覆盖确认，正文含「上传并覆盖同名文件：/a.mp3」「云端已存在同名对象（2.0 KB…）」「覆盖前旧文件
     自动备份到 .backup/<时间戳>/a.mp3」，确认词未输入时**上传请求数为 0**；
  ② 输入「覆盖」后 multipart 里 `overwrite=true`，成功提示出现「旧文件已备份至 .backup/20261018-160000/a.mp3」；
  ③ 无同名时不弹确认、`overwrite=false` 直传；
  ④ `/cos/exists` 返回 500 → 提示「同名检测失败，已取消上传」且上传请求数为 0；
  ⑤ 服务端 409 → 显示「已拒绝覆盖上传」，不出现「已上传 a.mp3」「旧文件已备份至」。
- 缺陷复现证据（修复前）：调试用 Playwright 用例记录到 `ReferenceError: dangerConfirm is not defined`
  且 `.el-message-box` 数量为 0 —— 补 import 后同一断言链通过（5 passed）。
- 未达 verified 的部分（需人工抽查）：以上均为 mock COS 下的验证。真实桶未测：
  ① `copy_object` 对大对象（>5GB 简单复制上限）的行为；② `.backup` 目录在真实桶里的可见性与计费；
  ③ 覆盖上传的端到端体验。抽查步骤：在「云端存储 > 文件管理」进入一个已有 `a.mp3` 的目录，
  重传同名 `a.mp3` → 应弹确认并要求输入「覆盖」→ 确认后列表旁进入 `.backup/<时间戳>/` 应能看到旧文件。

## 本次回写

- T02608 云端存储重命名/移动仍是静默覆盖，需同名检测与覆盖快照（H19）—— 复用本单
  `object_exists` / `_snapshot_before_overwrite`，含文件夹移动的覆盖条数预览。
- T02609 `.backup` 快照缺恢复入口与保留策略，回退仍需人工重传 —— 恢复动作 + 保留 N 份 + 审计。
- T02610 admin-web 无 ESLint，调用未导入的 util 只能靠 E2E 偶然暴露 —— 引入 `no-undef` 类静态门禁。

## 下一步建议

1. 真实桶冒烟：配好 COS 后跑一次同名覆盖，确认 `.backup` 可浏览、可下载、可回收（仅观察不建单，
   已并入 T02609 的验收步骤）。
2. 若运营需要「多版本长期保留」，应改为开启桶版本控制而不是靠 `.backup` 目录（产品裁决，
   已作为 T02609 的替代方案写在其描述里，仅观察不建单）。
