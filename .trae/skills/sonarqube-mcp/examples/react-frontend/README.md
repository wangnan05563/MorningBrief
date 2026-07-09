# React Frontend - 纯前端项目配置示例

> **适用场景**：纯 React/TypeScript 前端项目（无后端或后端独立部署）。

## 包含内容

```
react-frontend/
├── config/
│   └── project_config.json       # 纯 React 项目配置
└── README.md                      # 本文件
```

## 配置特点

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 前端语言 | TypeScript + JavaScript | |
| 启用的框架 | React | 自动识别 Hooks 误报 |
| 前端路径 | `src` | 标准 React 项目结构 |
| 测试命令 | `npm test -- --watchAll=false` | 仅前端测试 |
| 报告目录 | `docs/sonar-reports/` | 项目内归档 |
| 后端模块 | 无 | 纯前端项目 |

## 启用的硬约束

- **core.json**（14 条通用安全规则，包含 XSS 相关）
- **不启用任何业务规则**

## 使用方法

### 1. 复制到项目

```powershell
Copy-Item -Path "examples/react-frontend/config/project_config.json" -Destination ".trae/skills/sonarqube-mcp/config/project_config.json" -Force
```

### 2. 修改项目信息

```json
{
  "project": {
    "key": "my_react_frontend",     // 改为你的项目 key
    "name": "My React Frontend",    // 改为你的项目名
    "base_path": "."
  },
  "modules": {
    "frontend": {
      "path": "src",                 // 改为你的源码目录（Vite 通常是 src/）
      "languages": ["typescript", "javascript"],
      "frameworks": ["react"],
      "layers": {
        "components": "components",
        "pages": "pages",
        "hooks": "hooks",
        "utils": "utils",
        "services": "services",
        "types": "types",
        "store": "store"
      },
      "exclude": ["node_modules", "dist", "build", "__tests__"]
    }
  }
}
```

### 3. 验证

```powershell
.\verify-connection.ps1
```

### 4. 扫描

由于没有后端模块，需要确保 SonarQube 项目也仅包含前端代码：

```powershell
.\run-sonar-scanner.ps1 -Sources "src"
```

## 特殊配置：移除后端模块

如需完全移除 backend 节点（纯前端项目），删除 `modules.backend` 块即可。

`verify.test_command` 应改为仅前端命令：

```json
{
  "verify": {
    "test_commands": {
      "frontend": "npm test -- --watchAll=false"
    }
  }
}
```

## 预期扫描结果

- TypeScript/JavaScript 类型问题（S1128, S1854, S2681 等）
- React Hook 误报自动识别（typescript:S6488, S6486, S6759）
- 通用安全规则（XSS、敏感日志等）

## 适用项目类型

- ✅ React + TypeScript SPA
- ✅ Vite/CRA/Next.js 项目
- ✅ 组件库
- ✅ 管理后台前端
- ❌ 含后端的项目（请用 xianyu-hunter 示例）

## 相关文档

- [SKILL.md](../../SKILL.md)
- [framework_patterns.json](../../config/framework_patterns.json) — React 误报规则
