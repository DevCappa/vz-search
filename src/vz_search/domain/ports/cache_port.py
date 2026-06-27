from __future__ import annotations

from typing import Protocol, TypeVar

T = TypeVar("T")


class CachePort(Protocol):
    def get(self, key: str) -> T | None:
        ...

    def set(self, key: str, value: T) -> None:
        ...

    def delete(self, key: str) -> None:
        ...

    def clear(self) -> None:
        ...
