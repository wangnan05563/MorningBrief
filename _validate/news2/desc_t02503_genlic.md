来源：T02503（关于页外链与更新态可信 / FR-UX-404 / M101）

## 现状：门禁只是「挡住漂移」，没有消除手抄

T02503 给 `apps/admin-web/scripts/validate-nav.mjs` 加了依赖对账：
关于页那张手抄的开源清单（`About.vue` 里的 `const licenses = [...]`，当前 43 条 = 15 npm + 28 pip）
在构建期与 `apps/admin-web/package.json`、`backend/requirements.txt` 逐条比对，
三个方向的漂移都会让 `npm run build` 失败。实测证据（负向对照）：把 axios 改成 `^0.99.0`
并删掉 jieba 行，门禁立刻报 2 条并以 exit=1 结束。

但它仍是「人抄一遍，机器检查一遍」。真正省事的做法是**让机器生成那张表**，
人只维护许可证与仓库地址这两个清单里本来就没有的信息。

## 要做什么

1. 新增 `apps/admin-web/scripts/gen-licenses.mjs`：
   - 读 `package.json` 的 dependencies + devDependencies，用 `node_modules/<name>/package.json`
     里的 `license` / `licenses` 与 `repository.url` 填许可与仓库（前端已装依赖，无需联网）；
   - 读 `backend/requirements.txt` 的 `name==pin`，用
     `backend/.venv/Scripts/python.exe -m pip show <name>`（或 `pip-licenses`，若已安装）取
     License 与 Home-page；`[extras]` 与注释要剥掉；
   - 输出一段 JS 字面量覆盖 `About.vue` 里 `// <licenses>` 与 `// </licenses>` 之间的内容
     （用显式标记块，避免正则改代码）；取不到许可的包**保留条目并把 license 标为
     `未知（需人工确认）`**，不要静默丢弃——静默丢弃会让合规清单看起来是完整的。
2. `package.json` 增加 `"gen:licenses": "node scripts/gen-licenses.mjs"`，
   并在 `validate:nav` 之后提示「生成后需重跑 test:nav」。
3. 保留现有对账门禁作为兜底：即使有人手改了表，构建仍会失败。

## 验收

- `node scripts/gen-licenses.mjs` 跑完后 `npm run validate:nav` 与 `npm run test:nav` 均通过
  （即生成结果与两份清单零漂移）；
- 生成表条目数 == npm 依赖数 + requirements 去重后的包数（打印出来核对）；
- 至少 3 个已知特殊许可（PyMuPDF 的 AGPL-3.0、slowapi 的 MIT、cos-python-sdk-v5）
  在生成结果里许可名正确；
- 「许可取不到 → 标注未知」的分支有一条真实样例或 fixture 证明，不是只在注释里宣称。
