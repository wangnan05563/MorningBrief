# 评估明细页面折叠/展开优化设计

- **日期**: 2026-06-27
- **主题**: 评估明细菜单全面优化 —— 右侧分析面板折叠/展开 + 列表自适应扩展 + 视觉层次精修
- **状态**: 待实现

## 1. 背景与动机

评估明细页面（`frontend/src/pages/Evaluations/index.tsx`，1663 行）已实现完整的右侧分析面板，包含 5 个模块：
- 评估分布热力图（`EvalHeatmap.tsx`）
- 结果分析饼图（`ResultBarChart.tsx`）
- 分数分布直方图（`PriceHistogram.tsx`）
- 阈值建议 Card
- 阈值通过率计算器 Card

当前布局为固定 `<Row gutter={16}>` + `<Col span={16}>` 列表 + `<Col span={8}>` 图表列，**缺少折叠/展开机制**。用户在进行列表浏览、批量操作时，右侧面板占用 1/3 屏幕空间，限制了列表的可视信息密度。

本次优化目标：
1. 新增右侧面板的折叠/展开功能，折叠为窄竖条，列表自动扩展
2. 列表区域在折叠时显示更多列、加宽关键列，提升信息密度
3. 折叠状态持久化，记忆用户偏好
4. 整体视觉层次优化，保持专业感

## 2. 关键决策（已与用户确认）

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 折叠形态 | 折叠为窄竖条（1/24 宽），就地展开 | 不遮挡列表，列表空间大幅增加 |
| 默认状态 | 默认展开，状态持久化到 localStorage | 保持当前行为，专注列表时手动折叠 |
| 列表利用 | 折叠时自动显示更多列 + 加宽关键列 | 最大化利用多出的宽度 |

## 3. 架构设计

### 3.1 布局结构

```
当前:
<Row gutter={16}>
  <Col span={16}><Card>列表</Card></Col>
  <Col span={8}>5个Card</Col>
</Row>

优化后:
<Row gutter={16}>
  <Col span={panelCollapsed ? 23 : 16}>
    <Card extra={<折叠按钮/>}>列表</Card>
  </Col>
  <Col span={panelCollapsed ? 1 : 8}>
    {panelCollapsed ? <CollapsibleRail/> : <5个Card/>}
  </Col>
</Row>
```

### 3.2 新增组件 `CollapsibleRail.tsx`

折叠状态下的窄竖条组件，位于 `frontend/src/pages/Evaluations/components/CollapsibleRail.tsx`。

**职责**：在面板折叠时提供可视化的模块入口，点击任意图标触发展开。

**布局**（纵向）：
1. 顶部主按钮：`RightOutlined` 图标 + "展开"文字（纵向排列），点击展开面板
2. 分隔线
3. 5 个模块图标纵向排列：
   - `HeatMapOutlined` → 评估分布热力图
   - `PieChartOutlined` → 结果分析
   - `BarChartOutlined` → 分数分布
   - `AimOutlined` → 阈值建议
   - `CalculatorOutlined` → 阈值通过率计算器
4. 每个图标配 Tooltip 显示模块全名
5. 点击任意图标 = 展开面板（不滚动定位，保持简单）

**样式**：
- 宽度撑满 Col（约 40-50px）
- 背景色 `var(--xh-bg-code)` 与列表 Card 区分
- 左侧 1px 分隔线 `var(--xh-border-secondary)`
- 图标垂直居中，间距 16px
- hover 高亮：背景色变 `var(--xh-bg-hover)`（如有），否则 `rgba(24,144,255,0.06)`

**Props**：
```typescript
interface CollapsibleRailProps {
  onExpand: () => void  // 触发展开
}
```

### 3.3 状态管理

```typescript
// 持久化折叠状态，默认 false（展开）
const [panelCollapsed, setPanelCollapsed] = usePersistentState<boolean>(
  'xh.evals.panelCollapsed',
  false,
  { validator: (v): v is boolean => typeof v === 'boolean' },
)
```

复用现有 `usePersistentState` hook，与 `xh.evals.pageSize`、`xh.evals.columns` 等偏好键命名一致。

### 3.4 折叠按钮位置

折叠/展开按钮放在**列表 Card 的 extra 区域**（右上角），不占用列表内部空间。

- 折叠态：显示 `RightOutlined` + Tooltip "展开分析面板"
- 展开态：显示 `LeftOutlined` + Tooltip "收起分析面板"
- 按钮类型：`<Button type="text" size="small" icon={...} onClick={...} />`

### 3.5 列表列宽自适应

通过 `useMemo` 根据 `panelCollapsed` 派生最终列定义。**不修改 `useColumnConfig` hook**——折叠触发的列宽变化是系统行为，与用户手动配置的显隐/排序正交。

| 列 key | 展开时 | 折叠时 | 折叠时行为 |
|--------|--------|--------|-----------|
| task_id | width=120, responsive=['sm'] | width=120, 无 responsive | 强制显示 |
| title | width=200 | width=280 | 加宽减少截断 |
| seller | width=170 | width=220 | 加宽 |
| publish | width=160, responsive=['md'] | width=160, 无 responsive | 强制显示 |
| condition_tags | width=150 | width=180 | 加宽显示更多标签 |
| 其他列 | 原值 | 原值 | 不变 |

`SCROLL_X` 动态化：`panelCollapsed ? 2280 : 2020`（差额 = 80+50+50+30 = 210，预留缓冲）。

**实现方式**：
```typescript
const adaptedColumns = useMemo(() => {
  return columns.map(col => {
    if (!panelCollapsed) return col  // 展开态保持原样
    // 折叠态：应用列宽与 responsive 覆盖
    switch (col.key) {
      case 'task_id': return { ...col, responsive: undefined }
      case 'title': return { ...col, width: 280 }
      case 'seller': return { ...col, width: 220 }
      case 'publish': return { ...col, responsive: undefined }
      case 'condition_tags': return { ...col, width: 180 }
      default: return col
    }
  })
}, [columns, panelCollapsed])

// 最终传给 Table 的列
const visibleColumns = applyColumnConfig(adaptedColumns)
```

### 3.6 视觉层次优化（轻量）

1. **右侧 5 个 Card 统一间距**：当前阈值建议 Card 缺少 `marginTop`，统一为 `style={{ marginBottom: 16 }}`
2. **Card 标题加图标**：
   - 阈值建议：`AimOutlined`
   - 阈值通过率计算器：`CalculatorOutlined`
   - 热力图/饼图/直方图组件内部已有标题，不改
3. **折叠过渡**：Col 的 span 变化是离散的，给内部 Card 容器加 `transition: all 0.2s ease` 柔化突兀感
4. **统计卡片行**：6 个 `Col span={4}` 不变，Card 增加 `hover` 阴影 `box-shadow: 0 2px 8px rgba(0,0,0,0.08)` 提升交互感

## 4. 不做的事（YAGNI）

- ❌ 不重构 1663 行的 index.tsx 为多文件（当前任务不需要）
- ❌ 不抽取通用 `<CollapsiblePanel>` 组件（仅此一处使用）
- ❌ 不修改后端 API（5 个模块数据源已就绪）
- ❌ 不新增 echarts 图表类型（复用现有 4 个图表组件）
- ❌ 不改 `useColumnConfig` hook（折叠列宽是独立关注点）
- ❌ 不新增单元测试（纯 UI 布局变化，手动验证更高效）

## 5. 改动文件清单

| 文件 | 改动类型 | 预估行数 | 说明 |
|------|---------|---------|------|
| `frontend/src/pages/Evaluations/index.tsx` | 修改 | +30 / -5 | 新增 panelCollapsed 状态、动态 Col span、动态列宽、折叠按钮 |
| `frontend/src/pages/Evaluations/components/CollapsibleRail.tsx` | 新建 | ~60 | 折叠态竖条组件 |

## 6. 测试策略

### 6.1 手动验证清单
- [ ] 折叠按钮点击：面板折叠为竖条，列表扩展到 23/24
- [ ] 展开按钮点击：面板恢复 8/24，列表回到 16/24
- [ ] 刷新页面：折叠状态保持（localStorage 持久化）
- [ ] 折叠态列宽：task_id、publish 强制显示，title/seller/condition_tags 加宽
- [ ] 竖条图标 hover：Tooltip 显示模块名，背景高亮
- [ ] 竖条图标点击：展开面板
- [ ] 响应式断点：768px / 1024px / 1440px / 1920px 下布局正常
- [ ] 与列配置弹窗兼容：折叠态下手动隐藏列仍生效
- [ ] 与批量操作工具条兼容：折叠态下选中行工具条正常显示
- [ ] 与展开行兼容：折叠态下 expand 展开行内容正常

### 6.2 现有测试
- 检查 `frontend/src/pages/Evaluations/` 下是否有 vitest 测试，跑通
- `npm run build` 通过（TypeScript 类型检查）

### 6.3 不新增测试的理由
纯 UI 布局变化，涉及视觉呈现与交互手感，单元测试难以有效覆盖，手动验证更高效且可靠。

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 列宽切换导致表格重排闪烁 | antd Table 内置过渡，可接受；必要时加 `transition` |
| 折叠态下窄屏（<768px）竖条过窄 | 窄屏本就走横向滚动，竖条 1/24 在窄屏下约 30px 仍可点击 |
| 与列配置持久化冲突 | 折叠列宽是 `useMemo` 派生，不写入 `useColumnConfig` 的 hidden/order，正交无冲突 |

## 8. 后续可扩展方向（不在本次范围）

- 折叠态竖条图标点击后展开并滚动定位到对应模块
- 抽取通用 `<CollapsiblePanel>` 组件供其他页面复用
- 双击折叠按钮快速进入"专注模式"（隐藏所有非必要 UI）
