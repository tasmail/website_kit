"""Sample products and their illustrations, as pure data and pure functions (no Frappe).

The ten items are generic goods with invented names; every picture is an SVG drawn here from a few shapes and a fixed
palette, so nothing is downloaded and no third-party image ships in the app. `shop.py` turns this data into records that all
carry the tag field `website_kit_sample`.
"""

TAG_FIELD = "website_kit_sample"
ITEM_GROUP = "Sample"
FILE_PREFIX = "wk-sample-"
SIZE = (480, 360)

# slug, kind of drawing, background, main colour, accent colour, price, {lang: (name, description)}
ITEMS = (
	("mug", "mug", "#f3e8dc", "#b45309", "#fde68a", 180, {"en": ("Ceramic mug", "A 300 ml mug with a thick glaze."), "uk": ("Керамічна чашка", "Чашка 300 мл із товстою глазур'ю.")}),
	("tote", "bag", "#e0efe6", "#166534", "#bbf7d0", 240, {"en": ("Linen tote bag", "A roomy bag of washed linen."), "uk": ("Лляна сумка", "Містка сумка з прального льону.")}),
	("notebook", "book", "#e2e8f0", "#1e3a8a", "#bfdbfe", 120, {"en": ("Dotted notebook", "A5, 120 pages, sewn binding."), "uk": ("Блокнот у крапку", "А5, 120 сторінок, зшитий.")}),
	("lamp", "lamp", "#fef3c7", "#92400e", "#fcd34d", 650, {"en": ("Desk lamp", "A warm light for a work table."), "uk": ("Настільна лампа", "Тепле світло для робочого столу.")}),
	("candle", "candle", "#fde2e4", "#9f1239", "#fecdd3", 150, {"en": ("Soy candle", "A hand-poured candle, 40 hours."), "uk": ("Соєва свічка", "Свічка ручного виливання, 40 годин.")}),
	("scarf", "scarf", "#ede9fe", "#5b21b6", "#ddd6fe", 520, {"en": ("Wool scarf", "A soft scarf of fine wool."), "uk": ("Вовняний шарф", "М'який шарф із тонкої вовни.")}),
	("bottle", "bottle", "#dbeafe", "#075985", "#bae6fd", 330, {"en": ("Steel bottle", "A 600 ml bottle that keeps the cold."), "uk": ("Сталева пляшка", "Пляшка 600 мл, що тримає холод.")}),
	("clock", "clock", "#f1f5f9", "#334155", "#cbd5e1", 480, {"en": ("Wall clock", "A silent clock, 30 cm."), "uk": ("Настінний годинник", "Тихий годинник, 30 см.")}),
	("plant-pot", "pot", "#ecfccb", "#3f6212", "#d9f99d", 210, {"en": ("Plant pot", "A clay pot with a saucer."), "uk": ("Горщик для рослин", "Глиняний горщик із піддоном.")}),
	("board", "board", "#fef9c3", "#854d0e", "#fde047", 390, {"en": ("Cutting board", "An oak board, 40 by 25 cm."), "uk": ("Обробна дошка", "Дубова дошка 40 на 25 см.")}),
)  # fmt: skip


def item_code(slug: str) -> str:
	return "WK-SAMPLE-" + slug.upper()


def file_name(slug: str) -> str:
	return f"{FILE_PREFIX}{slug}.svg"


def text_for(entry: tuple, lang: str) -> tuple[str, str]:
	"""The name and the description in the site language, English when there is no translation."""
	texts = entry[6]
	return texts.get(lang[:2] if lang else "en", texts["en"])


def _shape(kind: str, main: str, accent: str) -> str:
	if kind == "mug":
		return (
			f'<rect x="170" y="130" width="130" height="120" rx="14" fill="{main}"/>'
			f'<path d="M300 150h28a28 28 0 0 1 0 56h-28" fill="none" stroke="{main}" stroke-width="16"/>'
			f'<rect x="182" y="142" width="106" height="14" rx="7" fill="{accent}"/>'
		)
	if kind == "bag":
		return (
			f'<rect x="160" y="150" width="160" height="150" rx="10" fill="{main}"/>'
			f'<path d="M200 150v-30a40 40 0 0 1 80 0v30" fill="none" stroke="{main}" stroke-width="14"/>'
			f'<rect x="190" y="200" width="100" height="40" rx="6" fill="{accent}"/>'
		)
	if kind == "book":
		return (
			f'<rect x="165" y="80" width="150" height="200" rx="8" fill="{main}"/>'
			f'<rect x="165" y="80" width="18" height="200" fill="{accent}"/>'
			f'<rect x="205" y="120" width="86" height="12" rx="6" fill="{accent}"/>'
			f'<rect x="205" y="146" width="60" height="12" rx="6" fill="{accent}"/>'
		)
	if kind == "lamp":
		return (
			f'<path d="M200 130h80l22 60h-124z" fill="{main}"/>'
			f'<rect x="236" y="190" width="8" height="90" fill="{main}"/>'
			f'<ellipse cx="240" cy="290" rx="50" ry="10" fill="{main}"/>'
			f'<ellipse cx="240" cy="200" rx="30" ry="8" fill="{accent}"/>'
		)
	if kind == "candle":
		return (
			f'<rect x="205" y="150" width="70" height="120" rx="8" fill="{main}"/>'
			f'<rect x="237" y="130" width="6" height="22" fill="{main}"/>'
			f'<path d="M240 90c18 22 14 36 0 40c-14-4-18-18 0-40z" fill="{accent}"/>'
		)
	if kind == "scarf":
		return (
			f'<path d="M150 120h180v50h-120l-10 130h-50z" fill="{main}"/>'
			f'<rect x="150" y="140" width="180" height="10" fill="{accent}"/>'
			f'<rect x="150" y="285" width="50" height="10" fill="{accent}"/>'
		)
	if kind == "bottle":
		return (
			f'<rect x="222" y="70" width="36" height="40" rx="6" fill="{accent}"/>'
			f'<rect x="200" y="106" width="80" height="180" rx="30" fill="{main}"/>'
			f'<rect x="214" y="150" width="52" height="60" rx="6" fill="{accent}"/>'
		)
	if kind == "clock":
		return (
			f'<circle cx="240" cy="180" r="100" fill="{main}"/><circle cx="240" cy="180" r="84" fill="{accent}"/>'
			f'<path d="M240 180V120M240 180l40 20" stroke="{main}" stroke-width="8" stroke-linecap="round"/>'
		)
	if kind == "pot":
		return (
			f'<path d="M180 160h120l-16 120h-88z" fill="{main}"/><rect x="172" y="146" width="136" height="22" rx="6" fill="{accent}"/>'
			f'<path d="M240 146c-30-30-10-60 0-70c10 10 30 40 0 70z" fill="{main}"/>'
		)
	return (  # board
		f'<rect x="130" y="130" width="220" height="110" rx="18" fill="{main}"/>'
		f'<circle cx="170" cy="150" r="9" fill="{accent}"/><rect x="200" y="168" width="120" height="8" rx="4" fill="{accent}"/>'
	)


def illustration(kind: str, background: str, main: str, accent: str, label: str = "") -> str:
	"""A 480 by 360 SVG picture; `label` becomes the accessible title (escaped)."""
	from html import escape

	width, height = SIZE
	title = f"<title>{escape(label)}</title>" if label else ""
	return (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">'
		f'{title}<rect width="{width}" height="{height}" fill="{background}"/>'
		f'<ellipse cx="240" cy="300" rx="130" ry="14" fill="#000" opacity=".08"/>{_shape(kind, main, accent)}</svg>'
	)


def svg_for(entry: tuple, lang: str = "en") -> str:
	slug, kind, background, main, accent, _price, _texts = entry
	return illustration(kind, background, main, accent, text_for(entry, lang)[0])
