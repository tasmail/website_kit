"""The safety net for a site that was moved to a new release without a migrate (Press calls that a "Pull")."""

from website_kit.pages import policy


def test_a_site_is_stale_until_its_sync_recorded_the_running_release():
	assert policy.sync_is_stale({}, "0.3.1")  # a site synced before the run was recorded
	assert policy.sync_is_stale({"_sync": {"version": "0.3.0", "builder": True}}, "0.3.1")
	assert not policy.sync_is_stale({"_sync": {"version": "0.3.1", "builder": True}}, "0.3.1")
	assert not policy.sync_is_stale(
		{"_sync": {"version": "0.3.1", "builder": False}}, "0.3.1"
	)  # no Builder: nothing to heal
	assert policy.sync_is_stale({"_sync": "junk"}, "0.3.1")
	assert policy.sync_is_stale(None, "0.3.1")


def test_the_heal_job_is_hourly_and_cheap():
	from pathlib import Path

	hooks = (Path(__file__).resolve().parent.parent / "website_kit" / "hooks.py").read_text(encoding="utf-8")
	assert "scheduler_events" in hooks and "website_kit.install.heal" in hooks
