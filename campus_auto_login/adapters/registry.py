from __future__ import annotations

from .base import PortalAdapter
from .drcom import DrComEportalAdapter
from .generic import GenericFormAdapter
from .h3c import H3CAdapter
from .ruijie import RuijieAdapter
from .srun import SrunAdapter


ADAPTERS: list[PortalAdapter] = [
    DrComEportalAdapter(),
    SrunAdapter(),
    RuijieAdapter(),
    H3CAdapter(),
    GenericFormAdapter(),
]


def iter_adapters() -> list[PortalAdapter]:
    return list(ADAPTERS)


def get_adapter(adapter_id: str) -> PortalAdapter:
    for adapter in ADAPTERS:
        if adapter.adapter_id == adapter_id:
            return adapter
    raise KeyError(f"未知协议适配器: {adapter_id}")
