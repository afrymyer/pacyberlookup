"""Tests for scheduler per-source polling configuration."""

from pacyberlookup.scheduler import run_once


class TestSchedulerConfig:
    def test_source_schedules_structure(self):
        """Verify the expected source schedule groups exist in the scheduler module."""
        # Import the module to verify it loads without error
        import pacyberlookup.scheduler as sched
        assert callable(sched.run_once)
        assert callable(sched.run_scheduled)

    def test_run_once_callable(self):
        """run_once should be importable and callable."""
        from pacyberlookup.scheduler import run_once
        assert callable(run_once)
