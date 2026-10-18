来源：T02493

T02493 已在后端落地「对象存在性检查」`GET /admin/api/v1/cos/exists` 与「覆盖前自动
快照」，但 `POST /cos/move`（重命名/移动）仍是旧行为：目标 Key 已存在时直接
copy_object + delete_object，把目标对象静默换掉（UX 评审 H9 的同族条目 H19）。

要做：
1. `move_object` 在执行前对目标 Key 做存在性检查（复用 `CosStorageService.object_exists`）；
2. 目标已存在且未确认覆盖 → 业务码 409（HTTP 200 + 信封），message 点名目标 Key 与大小；
3. 确认后先对目标对象做 `.backup/<时间戳>/` 快照（复用 `_snapshot_before_overwrite`），再复制+删除；
4. 路由补 `overwrite: bool = False` 入参，前端 `moveCosObject` 与 `CosFiles.vue` 的重命名/移动
   入口接入 `dangerConfirm`（动作+对象+条数+不可逆声明，与 T02490 口径一致）；
5. 文件夹移动是批量覆盖：确认框需列出「将被覆盖的对象条数」，条数来自服务端预览而非前端估算。

验证：后端单测（存在/不存在/覆盖快照/中止路径）+ 路由冒烟 + Playwright 覆盖确认框实测。
