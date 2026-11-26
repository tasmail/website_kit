"""Upgrade policy 5.8: a customer's edit is never overwritten by a release."""

from website_kit.pages import policy
from website_kit.pages.policy import ADOPT, CREATE, DELETED, DRAFT, KEEP, NOTE, ROUTE_TAKEN, UPDATE, decide

STATE = {"hash": "h1", "modified": "2026-01-01 10:00:00"}


def d(**kwargs):
	defaults = {"exists": True, "state": STATE, "modified": "2026-01-01 10:00:00", "shipped_hash": "h1"}
	return decide(**{**defaults, **kwargs}).action


def test_a_missing_object_is_created_once():
	assert d(exists=False, state=None, modified=None) == CREATE
	assert d(exists=False, modified=None) == DELETED  # shipped before, so the customer deleted it
	assert d(exists=False, state=None, modified=None, route_taken=True) == ROUTE_TAKEN


def test_nothing_changes_when_the_shipped_version_is_the_same_even_if_edited():
	assert d() == KEEP
	assert d(modified="2026-02-02 10:00:00") == KEEP


def test_an_unedited_object_is_updated_in_place():
	assert d(shipped_hash="h2") == UPDATE


def test_an_edited_page_gets_a_draft_next_to_it_and_only_once():
	assert d(shipped_hash="h2", modified="2026-02-02 10:00:00") == DRAFT
	drafted = {**STATE, "drafted": "h2"}
	assert d(shipped_hash="h2", modified="2026-02-02 10:00:00", state=drafted) == KEEP
	assert d(shipped_hash="h3", modified="2026-02-02 10:00:00", state=drafted) == DRAFT  # a still newer version


def test_an_edited_component_is_left_alone_and_reported():
	assert decide(exists=True, state=STATE, modified="x", shipped_hash="h2", has_draft=False).action == NOTE


def test_an_existing_record_without_state_is_adopted_if_identical_else_treated_as_edited():
	assert d(state=None, current_hash="h1") == ADOPT
	assert d(state=None, current_hash="other") == DRAFT
	assert d(state=None, current_hash=None) == DRAFT
	assert (
		decide(exists=True, state=None, modified="x", shipped_hash="h1", current_hash="zz", has_draft=False).action
		== NOTE
	)


def test_the_state_after_each_action():
	create = policy.next_state(None, policy.Decision(CREATE), "h1", "m1")
	assert create == {"hash": "h1", "modified": "m1"}
	assert policy.next_state(create, policy.Decision(UPDATE), "h2", "m2") == {"hash": "h2", "modified": "m2"}
	drafted = policy.next_state(create, policy.Decision(DRAFT), "h2", "later")
	assert drafted == {"hash": "h1", "modified": "m1", "drafted": "h2"}
	foreign = policy.next_state(None, policy.Decision(DRAFT), "h2", "x")
	assert foreign["drafted"] == "h2" and foreign["hash"] == ""
	assert policy.next_state(create, policy.Decision(KEEP), "h1", "m1") == create
	assert policy.next_state(None, policy.Decision(ROUTE_TAKEN), "h1", None) is None
	assert policy.next_state(create, policy.Decision(DELETED), "h1", None) == create


def test_names_of_drafts_are_stable():
	assert policy.draft_name("wk-home-uk", "abcdef123") == "wk-home-uk-new-abcdef"
	assert policy.draft_route("/home/", "abcdef123") == "kit-drafts/home-abcdef"


def test_notes_are_one_line_each_without_repeats_and_bounded():
	line = policy.note_line("wk-home-uk", policy.Decision(DRAFT), "wk-home-uk-new-abc")
	assert "wk-home-uk-new-abc" in line and policy.note_line("x", policy.Decision(KEEP)) == ""
	assert "route" in policy.note_line("p", policy.Decision(ROUTE_TAKEN)) and "edited" in policy.note_line(
		"c", policy.Decision(NOTE)
	)
	merged = policy.merge_notes("a\nb", ["b", "c", ""])
	assert merged == "a\nb\nc"
	big = policy.merge_notes("\n".join(f"line {n} " + "x" * 90 for n in range(100)), ["new"])
	assert len(big) <= policy.NOTE_LIMIT and big.endswith("new")


def test_home_page_changes_never_replace_a_choice():
	assert policy.home_page_changes("", None, "home") == {
		"website_settings.home_page": "home",
		"builder_settings.home_page": "home",
	}
	assert policy.home_page_changes("shop", "", "home") == {"builder_settings.home_page": "home"}
	assert policy.home_page_changes("shop", "shop", "home") == {}
