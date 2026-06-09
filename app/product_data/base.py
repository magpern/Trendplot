from typing import Any, Protocol


class ProductDataProvider(Protocol):
    """Future boundary for grounding article content in product data."""

    async def get_product_by_url(self, product_url: str) -> dict[str, Any] | None:
        ...

    async def get_product_storage_guidance(self, product_url: str) -> dict[str, Any] | None:
        ...

    async def get_product_category(self, product_url: str) -> dict[str, Any] | None:
        ...

    async def get_related_products(self, product_url: str) -> list[dict[str, Any]]:
        ...


class NullProductDataProvider:
    provider_name = "null-product-data"

    async def get_product_by_url(self, product_url: str) -> dict[str, Any] | None:
        return None

    async def get_product_storage_guidance(self, product_url: str) -> dict[str, Any] | None:
        return None

    async def get_product_category(self, product_url: str) -> dict[str, Any] | None:
        return None

    async def get_related_products(self, product_url: str) -> list[dict[str, Any]]:
        return []
