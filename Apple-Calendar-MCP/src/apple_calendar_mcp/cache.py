from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheItem(Generic[T]):
    value: T
    expires_at: datetime


@dataclass
class SimpleCache(Generic[T]):
    ttl_seconds: int = 60
    _items: dict[str, CacheItem[T]] = field(default_factory=dict)

    def get(self, key: str) -> T | None:
        item = self._items.get(key)
        if item is None:
            return None
        if item.expires_at <= datetime.now():
            self._items.pop(key, None)
            return None
        return item.value

    def set(self, key: str, value: T) -> None:
        self._items[key] = CacheItem(value=value, expires_at=datetime.now() + timedelta(seconds=self.ttl_seconds))
