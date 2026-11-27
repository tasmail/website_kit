"""One hash of everything a release ships to a site: the Builder pages and components, the Web Templates, the stylesheets, the
file-uploader guard and the translation files. Pure (no Frappe). `tests/test_content_lock.py` pins it next to `__version__`."""

import hashlib
from pathlib import Path

from . import stockpage
from .pages import specs

PKG = Path(__file__).resolve().parent
FILE_GLOBS = (
	"website_kit/web_template/*/*.html",
	"website_kit/web_template/*/*.json",
	"public/css/*.css",
	"translations/*",
)


def normalise(data: bytes) -> bytes:
	"""Line endings are not content (a Windows checkout must give the same hash)."""
	return data.replace(b"\r\n", b"\n")


def parts(extra: dict | None = None) -> dict[str, str]:
	"""`{name: digest}` for every shipped thing."""
	found = {f"{spec['kind']}:{spec['name']}": spec["hash"] for spec in specs.all_specs()}
	for pattern in FILE_GLOBS:
		for path in sorted(PKG.glob(pattern)):
			if path.is_file():
				found[f"file:{path.relative_to(PKG).as_posix()}"] = hashlib.sha256(
					normalise(path.read_bytes())
				).hexdigest()
	found["stockpage.guard"] = hashlib.sha256(stockpage.GUARD_SCRIPT.encode()).hexdigest()
	found.update(extra or {})
	return found


def shipped_hash(extra: dict | None = None) -> str:
	text = "\n".join(f"{name}={digest}" for name, digest in sorted(parts(extra).items()))
	return hashlib.sha256(text.encode()).hexdigest()[:16]
