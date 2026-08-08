# 复盘：配置加载 / 安装包完整性 / HLS 冷启动 / 微信隐私合规（2026-08-05）

> 本复盘基于本轮会话中解决的四个真实问题：
> 1. **PyInstaller frozen exe 微信登录 appid missing** —— `config.py` 的 `env_file` 路径在 `_MEIPASS` 临时目录解析失败，读不到 `.env`；
> 2. **重打包后 appid 仍 missing** —— `installer.iss` 的 `Excludes` 静默丢弃了 `.env`，包内无该文件；
> 3. **小程序音频"播放失败→成功"** —— HLS 首播冷启动失败，需静默重试 + mp3 回退；
> 4. **`setClipboardData:fail api scope is not declared`** —— 微信后台未声明「剪贴板」隐私 scope，复制文案在真机失败。
>
> 采用 **Sequential Thinking（分步推理）** 完成：先逐层拆解成功步骤，再识别不确定性与失败点，最后抽象出可固化的固定流程 / 判断逻辑与适用边界，并据此更新四个技能（news-code-dev / news-backend-code-review / news-frontend-code-review / news-auto-testing）。
> 提炼出的诊断标准见 [diagnostic-standards.md](diagnostic-standards.md) 的 **DS-11~DS-14**；对应编码规范见 news-code-dev `SKILL.md` 的 **规则 #196–#199**。

---

## 一、成功执行任务的完整步骤（维度 1，顺序不可颠倒）

| 问题 | 完整步骤（关键产出） |
|------|----------------------|
| P1 frozen 配置加载 | ① 复现：打包安装后微信登录报 appid missing，dev 模式正常 → 判定"部署态专属"；② 定位：`config.py` 的 `env_file=".env"` 依赖进程 cwd，exe 模式下 cwd 是 `_MEIPASS` 临时目录；③ 修复：`_resolve_env_file()` 按 `sys.frozen` 回退到 `sys.executable` 同级；④ 验证：`Settings().WX_APPID == 'wx1b4d58afd98bf2f6'`；⑤ 规范：沉淀 DS-11 |
| P2 安装包配置完整性 | ① 修好 P1 代码后仍 missing → 怀疑"包里没有 .env"；② 核查 `installer.iss`：`Excludes` 含 `.env`；③ 修复：移除排除项 + 显式 `Source: "dist\MorningBrief\.env"`；④ 构建脚本补 `attrib -H`；⑤ 验证：解包确认 `.env` 存在；⑥ 规范：沉淀 DS-12 |
| P3 HLS 冷启动 | ① 复现：首播失败、切集/重试后成功；② 定位：`BackgroundAudioManager` 首次播 HLS 冷启动 `onError`；③ 修复：`_retryHls()` + `MAX_HLS_RETRY=1` + `_applyProtocol()` 回退 mp3 + 连续 loading；④ 验证：首播失败自动恢复；⑤ 规范：沉淀 DS-13 |
| P4 微信隐私合规 | ① 复现：真机复制文案报 scope 未声明；② 定位：后台隐私清单缺"剪贴板"项（曾误搜"写入剪贴板"/`setClipboardData` 找不到）；③ 修复：`copyText` 改先 `requirePrivacyAuthorize`；④ 后台声明「剪贴板」scope；⑤ 规范：沉淀 DS-14 |

**关键教训**：P1 与 P2 是同一故障的"代码层"与"部署层"两面——只修代码不验包，或只验包不修代码，都会漏掉一半根因。正确顺序是 **先修代码路径（DS-11）→ 再验安装包是否真的把 `.env` 带进去了（DS-12）→ 解包实测**，二者缺一不可。

---

## 二、不确定性与失败点（维度 2）

| 失败点 | 触发条件 | 影响 | 根因 | 修复方式 |
|--------|----------|------|------|----------|
| 配置在 exe 模式读不到 | `env_file` 依赖 cwd，`sys.frozen` 时 cwd=`_MEIPASS` | 微信登录 appid missing | 相对路径在冻结态解析失败 | `sys.executable` 同级解析 `.env`（DS-11） |
| 包内缺 `.env` | `installer.iss` `Excludes` 含 `.env`；或 `Source:` 未显式包含 | 重打包仍 missing（代码已修但包无文件） | 排除项静默丢弃 + 未显式包含 | 移除排除 + 显式 `Source:`；`attrib -H`（DS-12） |
| HLS 首播失败被误判致命 | `onError` 直接 `showToast` + 停 loading | 用户看到报错、首播体验差 | 首次连接冷启动超时/解码延迟 | 静默重试 + mp3 回退 + 持续 loading（DS-13） |
| 隐私 scope 名称搜错 | 搜"写入剪贴板"/`setClipboardData` 找后台声明项 | 找不到声明入口，误以为已声明 | 后台类型名为「剪贴板」（读写同 scope） | 后台勾选「剪贴板」+ 调用前授权（DS-14） |

---

## 三、可抽象的固定流程与判断逻辑（维度 3）

```
配置相关故障通用诊断流程（命中即停）：
  exe 部署后"配置/凭据缺失"（如 appid missing）
    → 代码层：config.py 的 env_file 是否按 frozen 模式回退到 sys.executable 同级？
      ├─ 否 → 修复 _resolve_env_file（DS-11）
      └─ 是 → 部署层：解包安装包，确认 .env 是否真的在 {app} 目录？
            ├─ 否 → installer.iss Excludes 含 .env / 未 Source: 显式包含 → 修复（DS-12）
            └─ 是 → 其他（密钥内容错 / 环境变量覆盖）

小程序音频首播失败判断信号：
  grep audio.js onError：直接 showToast / 停 loading / 无 _retry / 无 mp3 回退
    → 命中即 CRITICAL（首播冷启动未做静默重试）

微信隐私接口判断信号：
  grep setClipboardData / getClipboardData 调用点
    → 代码侧调用前无 requirePrivacyAuthorize？命中 → 补授权
    → 后台隐私清单无「剪贴板」？命中 → 后台声明（注意名称是「剪贴板」非字面量）
```

**落地判断信号（grep）**：
- frozen 配置加载缺失：`env_file=` 为相对字符串且无 `getattr(sys, "frozen", False)` 分支
- 安装包配置缺失：`installer.iss` `Excludes` 含 `.env`/`*.env`，或 `Source:` 列表无 `.env`
- HLS 冷启动未防护：`onError` 处理函数无 `retry`/`MAX_HLS_RETRY`/`mp3` 回退
- 隐私 scope 未声明：`setClipboardData` 调用前无 `requirePrivacyAuthorize` / `onNeedPrivacyAuthorization`

---

## 四、适用场景与不适用场景（维度 4）

| 固定流程 / 判断逻辑 | 适用场景 | 不适用场景 |
|----------------------|----------|------------|
| `sys.executable` 同级解析 `.env` | PyInstaller / Nuitka 冻结 exe 部署 | 纯源码运行（解释器同级即 `.env`） |
| 安装包显式包含 `.env` | 含密钥/配置的安装包（包内依赖 `.env`） | 配置全部环境变量注入、包内无敏感文件 |
| HLS 首播静默重试 | 小程序/H5 用 `BackgroundAudioManager` 播 HLS(m3u8) | 纯本地 mp3 直链、无流式协商 |
| 微信隐私 scope 声明 | 微信小程序调用剪贴板/位置/相册等隐私接口 | 非微信平台、或接口无需隐私声明 |

---

## 五、本次沉淀的新编码标准（已整合进 news-code-dev / 审查技能）

| 编号 | 标准 | 优先级 | 对应审查维度 |
|------|------|--------|--------------|
| R196 / DS-11 | frozen 模式配置加载路径解析：`config.py` 必须按 `sys.frozen` 回退到 `sys.executable` 同级解析 `.env` | CRITICAL | 后端维度 203 |
| R197 / DS-12 | 安装包配置完整性：`installer.iss` 不得 `Excludes` 静默丢弃 `.env`、须显式 `Source:` 包含 + `attrib -H` | CRITICAL | 后端维度 204 |
| R198 / DS-13 | HLS 首播冷启动静默重试：音频 `onError` 须静默重试 + mp3 回退 + 持续 loading | HIGH | 前端维度 FE-199 |
| R199 / DS-14 | 微信隐私合规 scope 声明：`setClipboardData` 调用前 `requirePrivacyAuthorize`、后台声明「剪贴板」 | CRITICAL | 前端维度 FE-200 |

详细规则与 grep 判断信号见 [diagnostic-standards.md](diagnostic-standards.md) DS-11~DS-14；配置驱动实现见各审查技能的 `config.yaml`（`frozen_config_load_check` / `installer_secret_completeness_check` / `hls_cold_start_retry_check` / `wechat_privacy_scope_check`）与 news-auto-testing 的对应测试区块。
