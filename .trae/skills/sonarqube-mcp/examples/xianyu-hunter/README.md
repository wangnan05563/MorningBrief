# Xianyu Hunter - SonarQube 项目配置示例

> **适用场景**：FastAPI 后端 + React 前端的中大型项目，与 [xianyu-hunter](https://github.com/) 配套使用。

## 包含内容

```
xianyu-hunter/
├── config/
│   └── project_config.json       # Xianyu Hunter 项目配置
└── README.md                      # 本文件
```

## 配置特点

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 后端框架 | FastAPI | 自动识别装饰器误报 |
| 前端框架 | React | 自动识别 Hooks 误报 |
| 后端路径 | `src` | 标准 Python 项目结构 |
| 前端路径 | `frontend/src` | 标准 React 项目结构 |
| 测试命令 | `pytest tests/ ; cd frontend && npm test` | 分模块测试 |
| 报告目录 | `docs/04-系统维护/sonar-reports/` | 项目内归档 |

## 启用的硬约束

- **core.json**（14 条通用安全规则）
- **business/xianyu.json**（8 条 Xianyu 业务规则）
  - HMAC token 比较
  - WebView2 配置（DEVNULL/CREATE_NEW_CONSOLE/private_mode）
  - HF_ENDPOINT 镜像
  - 认证白名单完整性
  - fetch credentials
  - KBManager 白名单

## 使用方法

### 1. 复制到项目

```powershell
# 在你的项目根目录执行
Copy-Item -Path "examples/xianyu-hunter/config/project_config.json" -Destination ".trae/skills/sonarqube-mcp/config/project_config.json" -Force
```

### 2. 修改项目特定信息

编辑 `project_config.json`：

```json
{
  "project": {
    "key": "xianyu_hunter",        // 改为你的项目 key
    "name": "Xianyu Hunter",        // 改为你的项目名
    "base_path": "."
  }
}
```

### 3. 设置环境变量

```powershell
$env:SONAR_TOKEN = "squ_xxxxxxxxxxxxxxxxxx"   # 必需
$env:SONARQUBE_URL = "http://localhost:9000" # 可选
$env:JAVA_HOME_SONAR = "D:\tools\jdk17"      # 启动 SonarQube 需要
$env:SONARQUBE_HOME = "D:\tools\sonarqube"   # 启动 SonarQube 需要
```

### 4. 验证环境

```powershell
cd .trae\skills\sonarqube-mcp\scripts
.\verify-connection.ps1
```

## 预期输出

- `SonarQube URL : http://localhost:9000`
- `Project Key   : xianyu_hunter`
- `[通过] 端口 9000 正在监听`
- `SONAR_TOKEN : ***已配置***`

## 故障排除

| 现象 | 可能原因 | 解决方案 |
|------|----------|----------|
| 配置加载失败 | project_config.json 路径错误 | 确认在 `config/` 目录下 |
| 项目不存在 | SonarQube 未扫描该项目 | 先执行 `run-sonar-scanner.ps1` |
| Token 未设置 | 环境变量未配置 | `setx SONAR_TOKEN "squ_xxx"` |
| 端口未监听 | SonarQube 未启动 | 执行 `start-sonarqube.ps1` |

## 进阶配置

### 自定义修复策略覆盖

```json
{
  "fix_strategies_overrides": {
    "rule_overrides": {
      "python:S5857": "manual_review",
      "typescript:S6535": "skip"
    }
  }
}
```

### 自定义路径占位符

参考 `core_config.json -> path_placeholders`，在 `project_config.json` 中可通过 `${DOCS_DIR}` 引用。

## 相关文档

- [SKILL.md](../../SKILL.md) — 技能完整说明
- [scan-workflow.md](../../references/scan-workflow.md) — 扫描工作流
- [xianyu-rule-overrides.md](../../references/xianyu-rule-overrides.md) — Xianyu 规则覆盖
