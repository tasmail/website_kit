"""Own generated illustrations: inline SVG, themed by the `--wk-*` tokens, no external file, no photo, no font.

Each one is decorative (`aria-hidden`), so it needs no alt text and a screen reader skips it. Colours are token references in
`style` attributes, so a preset (the dark one included) restyles them.
"""

SVG_OPEN = (
	'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" width="100%" '
	'aria-hidden="true" focusable="false" style="max-inline-size:{max};block-size:auto">'
)
PRIMARY = "fill:var(--wk-color-primary)"
ACCENT = "fill:var(--wk-color-accent)"
SURFACE = "fill:var(--wk-color-bg)"
BORDER = "stroke:var(--wk-color-border);stroke-width:2"
MUTED = "fill:var(--wk-color-border)"


def _svg(box: str, max_width: str, body: str) -> str:
	return SVG_OPEN.format(box=box, max=max_width) + body + "</svg>"


def hero() -> str:
	"""A stylised dashboard: a window with bars, a ring and list lines."""
	return _svg(
		"0 0 480 360",
		"480px",
		f'<rect x="16" y="16" width="448" height="328" rx="20" style="{SURFACE};{BORDER}"/>'
		f'<rect x="16" y="16" width="448" height="48" rx="20" style="{PRIMARY}"/>'
		f'<rect x="16" y="44" width="448" height="20" style="{PRIMARY}"/>'
		f'<circle cx="48" cy="40" r="7" style="{SURFACE}"/><circle cx="72" cy="40" r="7" style="{SURFACE}"/>'
		f'<rect x="48" y="96" width="60" height="120" rx="8" style="{ACCENT}"/>'
		f'<rect x="124" y="136" width="60" height="80" rx="8" style="{PRIMARY}"/>'
		f'<rect x="200" y="112" width="60" height="104" rx="8" style="{ACCENT}"/>'
		f'<rect x="276" y="160" width="60" height="56" rx="8" style="{PRIMARY}"/>'
		f'<circle cx="400" cy="156" r="44" style="fill:none;stroke:var(--wk-color-border);stroke-width:18"/>'
		f'<circle cx="400" cy="156" r="44" style="fill:none;stroke:var(--wk-color-primary);stroke-width:18;'
		f'stroke-dasharray:180 277;transform:rotate(-90deg);transform-origin:400px 156px"/>'
		f'<rect x="48" y="244" width="240" height="14" rx="7" style="{MUTED}"/>'
		f'<rect x="48" y="272" width="180" height="14" rx="7" style="{MUTED}"/>'
		f'<rect x="48" y="300" width="212" height="14" rx="7" style="{MUTED}"/>'
		f'<rect x="352" y="244" width="80" height="70" rx="12" style="{ACCENT}"/>',
	)


def about() -> str:
	"""Stacked blocks: a small building made of cards."""
	return _svg(
		"0 0 360 280",
		"360px",
		f'<rect x="24" y="190" width="312" height="66" rx="14" style="{PRIMARY}"/>'
		f'<rect x="60" y="116" width="240" height="66" rx="14" style="{ACCENT}"/>'
		f'<rect x="108" y="42" width="144" height="66" rx="14" style="{SURFACE};{BORDER}"/>'
		f'<circle cx="64" cy="223" r="10" style="{SURFACE}"/><circle cx="96" cy="223" r="10" style="{SURFACE}"/>'
		f'<rect x="128" y="217" width="160" height="12" rx="6" style="{SURFACE}"/>'
		f'<rect x="92" y="143" width="176" height="12" rx="6" style="{SURFACE}"/>'
		f'<rect x="132" y="70" width="96" height="12" rx="6" style="{MUTED}"/>',
	)


def contact() -> str:
	"""An envelope."""
	return _svg(
		"0 0 320 220",
		"320px",
		f'<rect x="20" y="30" width="280" height="160" rx="18" style="{SURFACE};{BORDER}"/>'
		f'<path d="M24 46 L160 130 L296 46" style="fill:none;stroke:var(--wk-color-primary);stroke-width:10;'
		f'stroke-linecap:round;stroke-linejoin:round"/>'
		f'<circle cx="262" cy="52" r="26" style="{ACCENT}"/>'
		f'<rect x="254" y="38" width="16" height="20" rx="3" style="{SURFACE}"/>',
	)
