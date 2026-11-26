"""The shop menu rule as a pure function: the entry that leads to the shop is hidden while the shop has nothing to show."""

SHOP_URLS = ("/all-products",)


def is_shop_entry(item) -> bool:
	url = (item.get("url") if hasattr(item, "get") else getattr(item, "url", "")) or ""
	return url.rstrip("/") in SHOP_URLS


def visible_items(items, has_products: bool) -> list:
	"""The top bar items without the shop entry when no Website Item is published; the other items are kept as they are."""
	items = list(items or [])
	return items if has_products else [item for item in items if not is_shop_entry(item)]
