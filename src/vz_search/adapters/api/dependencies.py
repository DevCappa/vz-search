from __future__ import annotations

from vz_search.bootstrap import Container, build_container

_container: Container | None = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = build_container()
    return _container
