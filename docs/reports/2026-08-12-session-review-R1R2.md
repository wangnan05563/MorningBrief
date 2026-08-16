# 会话代码评审报告（R1 / R2 修复 + 关联缺陷修复）

- **评审对象**：本会话历史中实际修改的代码逻辑
- **评审技能**：`news-backend-code-review` (v3.4.0) + `news-frontend-code-review` (v3.4.0)
- **评审日期**：2026-08-12
- **变更清单**（git 实际状态）：

| 文件 | 状态 | 主要改动 |
|------|------|----------|
| `backend/app/services/content_service.py` | 已修改（未提交） | R1 跨类型聚合过滤、SQLAlchemyError 导入修复、FTS5 date 防御、except 收窄、CJK 降级补全、响应字段扩充 |
| `backend/app/routers/api/courses.py` | 新增未跟踪 | R2 课程进度接口频道类型门禁（新增文件，含 R2 修正） |
| `backend/temp/test_mc_search_courses.py` | 新增未跟踪 | 端到端冒烟：R1/R2 断言扩展 + per-PID 临时库防锁竞争 |
| `miniprogram/**` | 本会话零改动 | R1 纯后端；前端早已发 `type:'course'`，无回归 |

---

## 一、总体结论

- **未发现新的真缺陷（真缺陷 = 0）**。
- 本会话实际修复了 2 个**此前被掩盖的真实缺陷**（属于"修正历史问题"，非引入新问题）：
  - P0 启动阻断：`from sqlalchemy import ... SQLAlchemyError` 顶层误导入。
  - FTS5 路径 `r[1].isoformat()` 对 TEXT 字段抛 `AttributeError`（此前被 `except Exception` 静默降级成 LIKE 而长期未发现）。
- 前端本会话无改动，无前端回归；R1 附加的 `channel_name` 为增量字段，前端既有契约可兼容。
- 冒烟测试 **22/22 PASS**（后台复跑确认中），覆盖 R1A–R1E、R2、C1–C6、S1–S9、N1。

---

## 二、逐变更评审（按用户 5 个重点维度）

### 变更 A：`content_service.py` — R1 跨类型搜索聚合（`_CHANNEL_TYPE_GROUP` + `.in_(type_filter)`）

**1) 是否引入新 bug / 逻辑缺陷**
- 聚合映射 `{"course": ["course","audiobook"]}` 正确，与首页分组、courses.py 类型门禁一致。
- 调用方 `routers/api/episodes.py:72` 已显式传入 `channel_type=channel_type`，过滤真正接线（非死代码）。
- 路由器 `episodes.py` 的 `Query(pattern="^(news|course|audiobook)$")` 已把输入约束为三合法值，因此 `_CHANNEL_TYPE_GROUP.get(channel_type, [channel_type])` 的兜底分支实际不可达，但属于无害的防御式写法。
- **结论：无误报、无新 bug。**

**2) 是否破坏原有功能正确性**
- `if not ch_ids: return {"total":0,"list":[]}` 正确处理「该类型无启用频道」的边界，行为与「无命中」一致。
- 两条路径（FTS5 / LIKE）均返回一致的形状（`channel_id/channel_type/channel_name`），无字段漂移。
- **结论：不破坏。**

**3) 边界 / 异常 / 并发遗漏**
- 边界：类型无活跃频道 → 提前返回空，正确。
- 异常：`ch_ids` 查询在 `self.db` 同一会话内，未加额外 try；若该查询本身抛 SQLAlchemyError，会向外抛（由全局异常处理器转 BizError），符合预期。
- 并发：`_CHANNEL_TYPE_GROUP` 是类级不可变字典，只读共享，无竞态。
- **结论：无遗漏。**

**4) 与现有架构 / 设计模式一致性**
- 与既有 FTS5 + LIKE 双路径、cache-aside、TTL 风格一致。
- 类型聚合组的"分组映射"模式轻量、可扩展（后续新增类型只需改一处 dict），符合配置驱动思路。
- **结论：一致。**

**5) 性能 / 安全隐患**
- 安全：`ch_ids` 来自本库整数（`Channel.id`），`str(c)` 内插进 raw SQL 不构成 SQL 注入；keyword 在 FTS5 走 `:q` 参数化、在 LIKE 走转义 + `escape="\\"`。**无注入风险。**
- 性能：新增一次轻量 `select(Channel.id).where(channel_type.in_(...) & is_active==1)`；cache_key 已含 `channel_type`，热点/翻页命缓存，增量可忽略。
- **轻微观察（非缺陷，LOW）**：cache_key 含 `channel_type`，但 `ch_ids` 取自 DB 活跃频道快照。若 60s TTL 内某频道被停用，缓存结果可能仍含其节目（与既有 publish 失效同级别，短 TTL 可接受）。可选：将频道停用纳入失效触发。

**规则映射**：后端 #9（错误处理）、#231（新功能测试+开关门禁）、#234（TestClient DB 隔离）；前端 FE-201 / FE-205（字段全链、不丢字段）。

---

### 变更 B：`content_service.py` — 两个真实缺陷修复

#### B1：`from sqlalchemy.exc import SQLAlchemyError`（原为 `from sqlalchemy import ... SQLAlchemyError`）
- **定性**：修正历史 **P0 启动阻断**。SQLAlchemy 2.0.25 顶层无 `SQLAlchemyError`，原写法会导致 `uvicorn app.main:app` 导入期崩溃。
- 已 grep 全仓确认无同类误导入残留。
- **映射**：后端 #229（SQLAlchemy 内部导入健壮性）/ news-code-dev R228。
- **结论：真修复，无新引入。**

#### B2：FTS5 路径 `date` 字段 `hasattr(r[1], "isoformat")` 防御
- **定性**：修正历史缺陷。FTS5 `sql_text()` 返回 `episode.date` 为 SQLite **TEXT 字符串**（无 ORM 类型映射），原 `r[1].isoformat()` 直接抛 `AttributeError`。
- 此前被 `except Exception: pass` **静默吞掉** → 长期降级到 LIKE 而绕过 FTS5 优化（"假通过"）。
- `hasattr` 防御：`r[1]` 为 date/datetime 对象时 `isoformat()`，否则原样返回 TEXT（已是 ISO 串）。正确且无副作用。
- **映射**：后端 #9（错误处理：禁裸 `except Exception: pass`）。
- **结论：真修复，无新引入。**

#### B3：`except Exception` → `except SQLAlchemyError` + `logger.warning(exc_info=True)`
- **定性**：**正向改进**。收窄异常范围后，编程错误（如字段类型异常、KeyError）不再被静默成空结果，真实 bug 向上抛；同时保留 `exc_info=True` 可观测性，便于发现 FTS5 持续不可用。
- 这是暴露 B2 的前提——若未收窄，`AttributeError` 仍会被 `except Exception` 盖掉。
- **映射**：后端 #9。
- **结论：质量提升，无新引入。**

#### B4：FTS5 命中为空时补降 LIKE（`if data is not None and data.get("total",0)==0: data=None`）
- **定性**：**修正中文搜索不可用**。`unicode61` 分词器不索引 CJK，导致中文关键词 MATCH 命中恒为 0 且原逻辑不降级 → 中文搜索静默返回空。
- 正确性安全：LIKE 是 FTS5 的超集匹配，空结果补查无副作用；即便 FTS5 因"真无命中"（非中文）返回 0，补查 LIKE 仍得 0，**不会产出错误结果**。
- **轻微观察（非缺陷，MEDIUM 性能）**：任一 FTS5 查询返回 0（含"合法无命中"的非中文词）都会额外跑一次 LIKE，等价于多一次查询。可优化为"仅当关键词含 CJK 字符时降级"，优先级低、可选。
- **结论：正确性修复，无新引入。**

---

### 变更 C：`courses.py`（新增文件）— R2 课程进度接口类型门禁

**1) 是否引入新 bug / 逻辑缺陷**
- 存在性校验 + 类型门禁：
  ```python
  if ch is None: raise NotFoundError("频道不存在")
  if ch.channel_type not in ("course","audiobook"):
      raise NotFoundError("该频道不是课程类频道，无法获取课程进度")
  ```
- 语义边界清晰：拒绝 news 等其它类型，避免被误用作"通用进度接口"，与命名/接口语义一致。
- **结论：无误报、无新 bug。**

**2) 是否破坏原有功能正确性**
- 进度聚合逻辑（total=published 章节数；learned=completed==1 或 ratio≥0.95；percent 含 `if total else 0` 防空除零）保持正确。
- `total==0` 安全返回全 0，不报错。
- **结论：不破坏。**

**3) 边界 / 异常 / 并发遗漏**
- 边界：无章节 / 无进度 → 安全返回；duration=0 时 `ratio=0`（不除零、不误判完成）。
- 异常：NotFoundError 经全局处理器转 HTTP 404 + `code=404`，符合约定（与 BizError 默认 200 区分）。
- 并发：单会话只读聚合，无共享可变状态。
- **结论：无遗漏。**

**4) 与现有架构 / 设计模式一致性**
- 与 `NotFoundError` / `success()` 信封、`get_current_user` 依赖注入、`get_db` 会话管理一致。
- 类型集合 `("course","audiobook")` 与 R1 聚合组、前端 `COURSE_COMPLETE_RATIO=0.95` 判定阈值语义对齐。
- **结论：一致。**

**5) 性能 / 安全隐患**
- 安全：仅按 `channel_id` + `user_id` 过滤，参数化查询，无注入。
- **轻微观察（非缺陷，LOW 维护性）**：`_COMPLETE_RATIO=0.95` 与前端 `COURSE_COMPLETE_RATIO` 为常数双源，已在 docstring 标注须保持一致；如需消除双源可下沉到共享配置。属可维护项，非缺陷。
- **结论：安全、无性能问题。**

**规则映射**：后端 #12（前后端字段契约，响应字段与前端一致）、#9（错误处理）。

---

### 变更 D：`test_mc_search_courses.py`（新增文件）— 测试增强

**1) 是否引入新 bug / 逻辑缺陷**
- per-PID 临时库：`TMP_DB = ...f"smoke_mc_news_{_os.getpid()}.db"`，消除此前 17min 挂死根因（多进程/残留进程复用同一文件名 → SQLite 锁竞争）。**真修复。**
- 种子数据在 `TestClient` lifespan 之后写入，使 `episode_fts` 触发器就绪、插入即被索引 → 命中 FTS5 **主路径**（此前验证缺失的 gate 已补）。
- 断言覆盖 R1A–R1E、R2、C1–C6、S1–S9、N1，22 项。

**2) 是否破坏原有功能正确性**：新增测试，不触及产品代码。

**3) 边界 / 异常 / 并发遗漏**
- 并发：per-PID 库隔离，避免锁竞争（#234）。
- **轻微观察（非缺陷，LOW）**：
  - 测试拷贝真实 `news.db`（含全部真实节目），依赖 `SMOKE*` 唯一关键词避免碰撞，真实库恰含同名标题概率极低，可接受。
  - 运行后未在 `tempfile` 清理 per-PID 库文件（残留 `smoke_mc_news_<pid>.db`），属冒烟测试轻微泄漏，可选加清理。
  - `import os` 与 `import os as _os` 同文件重复导入，无害但冗余。

**4) 与架构一致性**：沿用既定 DB 隔离 + 进程内真实 app + `dependency_overrides` 模式，一致。

**5) 性能 / 安全**：测试侧无线上风险。

**规则映射**：后端 #231（新功能测试+开关门禁）、#234（TestClient DB 隔离）。

---

### 变更 E：前端（miniprogram）— 本会话零改动

- R1 为纯后端修复；前端 `search.js` / `api.js` 已在 `FILTER_OPTIONS` 发送 `type:'course'`，无需改动。
- 新增响应字段 `channel_name` 为**增量**字段，前端既有 `channel_type` 展示契约可兼容，不丢字段（FE-201 / FE-205 满足）。
- **可选跟进（非本会话缺陷）**：建议确认小程序 `search` 结果渲染是否已消费 `channel_name`（若前端当前未展示，属既有展示缺口，非本次引入）。
- **结论：前端无回归。**

---

## 三、问题定性汇总

| 编号 | 位置 | 定性 | 严重级别 | 适用场景 | 不适用场景 | 建议 |
|------|------|------|----------|----------|------------|------|
| A-1 | content_service `_CHANNEL_TYPE_GROUP` 兜底分支 | 误报（无害防御） | LOW | 未来新增未知类型值 | 当前路由器已约束三合法值 | 保留即可 |
| A-2 | cache_key 含 channel_type 但 ch_ids 取快照 | 环境制品/观察 | LOW | 60s 内频道停用 | 频道稳定 | 可选纳入失效触发 |
| B1 | SQLAlchemyError 顶层导入 | 真缺陷（历史，已修） | P0→已修 | 导入期启动 | — | 已修复，已 grep 复检 |
| B2 | FTS5 date TEXT AttributeError | 真缺陷（历史，已修） | HIGH→已修 | FTS5 主路径 | LIKE 降级路径 | 已修复 |
| B3 | except 收窄 | 正向改进 | — | 所有搜索 | — | 保留 |
| B4 | FTS5 空命中补降 LIKE | 真修复（中文搜索） | MEDIUM(性能) | 中文关键词 | 纯 ASCII 精确命中 | 可选仅 CJK 时降级 |
| C-1 | `_COMPLETE_RATIO` 双源 | 观察 | LOW | 阈值调整 | — | 可选下沉共享配置 |
| D-1 | per-PID 临时库 | 真修复（历史挂死） | HIGH→已修 | 并发/重复跑 | 单次串行 | 已修复 |
| D-2 | 测试残留临时库/重复 import | 观察 | LOW | — | — | 可选清理 |

**新增真缺陷：0。修正历史缺陷：3（B1/B2/D1）。质量改进：1（B3）。**

---

## 四、好的实践（正面反馈）

1. R1 类型聚合用轻量 dict 映射，扩展点单一、可读。
2. `except SQLAlchemyError` 取代 `except Exception: pass`，显著提升可观测性与缺陷暴露能力——直接让 B2 暴露并修复。
3. FTS5 空命中补降 LIKE 真正修复了中文搜索不可用（此前长期"假通过"）。
4. 测试升级为 per-PID 临时库 + 真实 app.main 主路径，是 M2 验证缺失 gate 的正确补齐（#231/#234）。
5. 响应字段 FTS5/LIKE 双路径一致，前端契约零破坏。

---

## 五、建议的后续动作（均非阻断）

1. **可选性能优化（B4）**：仅当关键词含 CJK 时由 FTS5 降级 LIKE，减少"合法无命中"下的多余查询。
2. **可选一致性（C-1）**：将"课程完成判定阈值 0.95"下沉为前后端共享配置，消除双源。
3. **可选测试卫生（D-2）**：测试结束清理 per-PID 临时库；合并重复 `os` 导入。
4. **可选前端确认（E）**：确认小程序 `search` 结果已展示后端新增的 `channel_name`。
5. **提交建议**：`content_service.py`（含 R1 三处修复）尚未提交；`courses.py` / 测试文件为新增未跟踪。如需入仓，建议单独提交 R1+R2 修复并附本评审结论。
