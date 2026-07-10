"""通知器注册表（对标 17_xianyu notifier/registry.py）。

注册表 + 工厂模式：
- _registry: dict[str, type[INotifier]] 字典映射 name→class
- register(name)：装饰器注册渠道类
- create(name, **kwargs)：工厂方法实例化渠道

新增渠道只需用 @registry.register("channel_name") 装饰类，
无需改动 Hub 或其他渠道代码。
"""
from __future__ import annotations

from typing import Type

from app.services.notifier.base import INotifier


class NotifierRegistry:
    """通知器注册表。

    使用装饰器模式注册渠道类，工厂方法按名称实例化。
    """

    def __init__(self) -> None:
        self._registry: dict[str, Type[INotifier]] = {}

    def register(self, name: str):
        """装饰器：注册渠道类到注册表。

        用法：
            @registry.register("wecom")
            class WeComNotifier(INotifier): ...
        """
        def decorator(cls: Type[INotifier]) -> Type[INotifier]:
            if not issubclass(cls, INotifier):
                raise TypeError(f"{cls.__name__} 必须继承 INotifier")
            self._registry[name] = cls
            return cls
        return decorator

    def create(self, name: str, **kwargs) -> INotifier:
        """工厂方法：按名称实例化渠道。

        未注册的名称抛 KeyError（调用方应先检查 contains）。
        """
        cls = self._registry.get(name)
        if cls is None:
            raise KeyError(f"通知渠道未注册: {name}")
        return cls(**kwargs)

    def contains(self, name: str) -> bool:
        """检查渠道是否已注册。"""
        return name in self._registry

    def list_channels(self) -> list[str]:
        """列出所有已注册的渠道名。"""
        return list(self._registry.keys())


# 全局注册表单例
registry = NotifierRegistry()
