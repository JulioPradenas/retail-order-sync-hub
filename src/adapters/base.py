"""Common interface and DTOs for marketplace adapters.

Every marketplace (MercadoLibre, Paris, ...) implements ``MarketplaceAdapter``,
so the outbox worker pushes orders without knowing which backend it talks to.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class OrderItemDTO(BaseModel):
    sku: str
    qty: int = Field(gt=0)


class OrderDTO(BaseModel):
    """Internal order representation handed to an adapter."""

    odoo_order_id: int
    buyer: str
    items: list[OrderItemDTO] = Field(min_length=1)
    external_ref: str


class PushResult(BaseModel):
    marketplace_order_id: str
    status: str


class AdapterError(Exception):
    """Typed adapter failure (transient unless ``permanent`` is set)."""

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


class MarketplaceAdapter(Protocol):
    name: str

    async def push_order(self, order: OrderDTO) -> PushResult: ...
    async def update_stock(self, sku: str, qty: int) -> None: ...
    async def get_order_status(self, marketplace_order_id: str) -> str: ...


def order_from_payload(payload: dict[str, Any]) -> OrderDTO:
    """Build an ``OrderDTO`` from a stored outbox payload."""
    return OrderDTO.model_validate(payload)
