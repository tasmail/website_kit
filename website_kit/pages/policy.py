"""Upgrade policy 5.8 for the shipped pages, components and script, as pure decisions (no Frappe import).

The kit remembers, per object, what it last shipped: `{"hash": <hash of the shipped version>, "modified": <modified of the
record right after the kit wrote it>}`. From that it can tell an unedited object (its `modified` is still the recorded one)
from one the customer touched, and a customer's edit is never overwritten:

| situation                                         | action                                                       |
| ------------------------------------------------- | ------------------------------------------------------------ |
| the record is missing, never shipped before        | create it                                                    |
| the record is missing, shipped before              | leave it missing (the customer deleted it)                   |
| the route is used by another page                  | skip and say so in the note                                  |
| the shipped version did not change                 | nothing                                                      |
| changed, the record is unedited                    | update it in place                                           |
| changed, the record was edited, a page             | write the new version as an unpublished draft next to it, once |
| changed, the record was edited, a component/script | leave it, say so in the note                                 |
| the record exists, nothing recorded, same content  | adopt it (record it, write nothing)                          |
| the record exists, nothing recorded, other content | treat it as the customer's: as an edited record              |
"""

from dataclasses import dataclass

CREATE = "create"
UPDATE = "update"
KEEP = "keep"
DRAFT = "draft"
NOTE = "note"  # an edited object that cannot have a draft: left alone, reported
ADOPT = "adopt"
DELETED = "deleted"
ROUTE_TAKEN = "route_taken"


@dataclass(frozen=True)
class Decision:
	action: str
	reason: str = ""


def decide(
	*,
	exists: bool,
	state: dict | None,
	modified: str | None,
	shipped_hash: str,
	current_hash: str | None = None,
	route_taken: bool = False,
	has_draft: bool = True,
) -> Decision:
	"""What to do with one shipped object.

	`state` is the recorded entry or None; `modified` the record's current `modified` as text; `current_hash` the hash of the
	record's content in the shipped form (to adopt an identical record); `has_draft` whether the kind can be written next to
	the customer's version (pages can, components and scripts cannot).
	"""
	if not exists:
		if state:
			return Decision(DELETED, "the record was deleted after the kit created it")
		if route_taken:
			return Decision(ROUTE_TAKEN, "another page already uses the route")
		return Decision(CREATE)
	edited_kind = DRAFT if has_draft else NOTE
	if not state:
		if current_hash is not None and current_hash == shipped_hash:
			return Decision(ADOPT)
		return Decision(edited_kind, "an existing record the kit did not create")
	if state.get("hash") == shipped_hash:
		return Decision(KEEP)
	if str(modified or "") == str(state.get("modified") or ""):
		return Decision(UPDATE)
	if state.get("drafted") == shipped_hash:
		return Decision(KEEP, "the new version was already written as a draft")
	return Decision(edited_kind, "the record was edited after the kit wrote it")


def next_state(state: dict | None, decision: Decision, shipped_hash: str, modified: str | None) -> dict | None:
	"""The state entry after the decision was carried out (`modified` is read after the write)."""
	state = dict(state or {})
	if decision.action in (CREATE, UPDATE, ADOPT):
		return {"hash": shipped_hash, "modified": str(modified or "")}
	if decision.action in (DRAFT, NOTE):
		state["drafted"] = shipped_hash
		state.setdefault("hash", state.get("hash", ""))
		state.setdefault("modified", state.get("modified", ""))
		return state
	return state or None


def draft_name(name: str, shipped_hash: str) -> str:
	return f"{name}-new-{shipped_hash[:6]}"


def draft_route(route: str, shipped_hash: str) -> str:
	return f"kit-drafts/{route.strip('/')}-{shipped_hash[:6]}"


def note_line(name: str, decision: Decision, draft: str | None = None) -> str:
	"""One line for the note of the settings page."""
	if decision.action == DRAFT:
		return (
			f"{name}: a new kit version was saved as the unpublished draft {draft}; your edited page was left as it is."
		)
	if decision.action == NOTE:
		return f"{name}: a new kit version is available, but the record was edited and was left as it is."
	if decision.action == ROUTE_TAKEN:
		return f"{name}: not created, another page already uses its route."
	return ""


NOTE_LIMIT = 2000


def merge_notes(existing: str | None, lines: list[str]) -> str:
	"""Append the new lines to the note without repeating one, keeping the newest within the limit."""
	have = [line for line in (existing or "").splitlines() if line.strip()]
	for line in lines:
		if line and line not in have:
			have.append(line)
	text = "\n".join(have)
	while len(text) > NOTE_LIMIT and len(have) > 1:
		have.pop(0)
		text = "\n".join(have)
	return text[-NOTE_LIMIT:]


def home_page_changes(website_home, builder_home, route: str) -> dict:
	"""Where the home route may be written: only a field that holds nothing. The customer's choice is never replaced."""
	changes = {}
	if not (website_home or "").strip():
		changes["website_settings.home_page"] = route
	if not (builder_home or "").strip():
		changes["builder_settings.home_page"] = route
	return changes
