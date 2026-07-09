# Basic Python - 最小 Python 项目配置示例

> **适用场景**：纯 Python 项目（CLI 工具、脚本库、数据处理），无特定 Web 框架。

## 包含内容

```
basic-python/
├── config/
│   └── project_config.json       # 最小 Python 项目配置
└── README.md                      # 本文件
```

## 配置特点

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 后端语言 | Python | 仅支持 Python |
| 启用的框架 | 无 | 不加载任何框架模式 |
| 后端路径 | `src` | 标准 Python 项目结构 |
| 测试命令 | `pytest tests/` | 仅后端测试 |
| 报告目录 | `docs/sonar-reports/` | 项目内归档 |

## 启用的硬约束

- **core.json**（14 条通用安全规则）
- **不启用任何业务规则**（`enabled_business_rules: []`）

## 使用方法

### 1. 复制到项目

```powershell
Copy-Item -Path "examples/basic-python/config/project_config.json" -Destination ".trae/skills/sonarqube-mcp/config/project_config.json" -Force
```

### 2. 修改项目信息

```json
{
  "project": {
    "key": "my_python_project",     // 改为你的项目 key
    "name": "My Python Project",    // 改为你的项目名
    "base_path": "."
  },
  "modules": {
    "backend": {
      "path": "src",                 // 改为你的源码目录
      "languages": ["python"],
      "frameworks": [],              // 留空：无框架模式
      "layers": {                    // 按需调整
        "core": "core",
        "utils": "utils",
        "models": "models"
      },
      "exclude": ["__pycache__", ".git", "dist", "build", "tests", "venv", ".venv"]
    }
  }
}
```

### 3. 设置环境变量（同 xianyu-hunter）

```powershell
$env:SONAR_TOKEN = "squ_xxxxxxxxxxxxxxxxxx"
```

### 4. 验证并扫描

```powershell
.\verify-connection.ps1
.\run-sonar-scanner.ps1
```

## 预期输出

- 加载 v2 配置（core+project）
- 仅加载 14 条核心安全规则
- 不进行任何框架误报识别

## 适用项目类型

- ✅ CLI 工具（如 `my-cli`）
- ✅ 脚本库（如 `my-utils`）
- ✅ 数据处理管道
- ✅ 算法实现
- ❌ Web 项目（请用 xianyu-hunter 或 react-frontend 示例）
- ❌ 多语言项目（请在 modules 中添加 frontend 节点）

## 进阶：添加 Web 框架

如需添加 FastAPI/Django 支持，修改 `modules.backend.frameworks`：

```json
{
  "modules": {
    "backend": {
      "frameworks": ["fastapi"]    // 或 ["django"]
    }
  }
}
```

框架模式会自动从 `config/framework_patterns.json` 加载。

## 相关文档

- [SKILL.md](../../SKILL.md)
- [framework_patterns.json](../../config/framework_patterns.json) — 可用框架列表
