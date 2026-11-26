"""The shop menu rule as a pure function: the entry that leads to the shop is hidden while the shop has nothing to show."""

from urllib.parse import urlsplit

SHOP_URLS = ("/all-products",)


def _get(item, key):
	value = item.get(key) if hasattr(item, "get") else getattr(item, key, "")
	return value or ""


def normalise(url) -> str:
	"""The path of a menu URL: no host, query, fragment or trailing slash, always with a leading slash, lower case."""
	path = urlsplit(str(url).strip()).path.strip().rstrip("/").lower()
	return "/" + path.lstrip("/") if path else ""


def is_shop_entry(item) -> bool:
	"""True for a menu item that links to the shop page, by `url` or `route`, also with a host, query or language prefix."""
	for key in ("url", "route"):
		path = normalise(_get(item, key))
		if any(path == shop or path.endswith(shop) for shop in SHOP_URLS):
			return True
	return False


def visible_items(items, has_products: bool) -> list:
	"""The top bar items without the shop entry while the shop is off or empty; the other items are kept as they are."""
	items = list(items or [])
	return items if has_products else [item for item in items if not is_shop_entry(item)]
