来源：T02489（FR-UX-201 应急停服可用性与状态可信）

问题：`backend/app/services/mobile_service.py:327 is_maintenance_enabled()` 是 **fail-open**——

```python
try:
    on = (await get_maintenance(db)).get("enabled", False)
except Exception as e:
    logger.warning("读取维护态失败，按非维护态处理: %s", e)
    on = False
```

注释写「保证安全默认」，但这里的「安全」方向与停服意图相反：维护态标志存在 `system_flag` 表，一旦数据库超时/连接异常（往往正是故障现场），值守管理员刚下的应急停服指令会被静默绕过，`workflow_scheduler.trigger_workflow`（`backend/app/services/workflow_scheduler.py:616`）照常放行新任务——恰好是最需要停服的时刻停不住。

建议改法（需确认口径后实施）：
1. 读库异常时优先采用最后一次已知缓存值（当前 TTL 5s 缓存只用于加速，异常路径没用到）；无已知值时按 fail-closed 拒绝触发新任务，并在返回体里给运维可辨识的原因。
2. 无论采用哪种，异常分支要升级日志等级并接入通知（通知管理模块已有 webhook 通道），不能只 `logger.warning`。
3. 补测试：模拟 `get_maintenance` 抛异常，断言 `trigger_workflow` 的行为与所选口径一致。

风险：改为 fail-closed 会让「数据库不可用」直接表现为「无法触发新任务」，需要与调度告警口径一起确认，避免误判为调度器故障。
