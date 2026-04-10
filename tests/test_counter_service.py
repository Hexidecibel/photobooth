"""Tests for CounterService."""

import pytest

from app.services.counter_service import CounterService


@pytest.fixture
def counter_service(tmp_path):
    return CounterService(data_dir=str(tmp_path))


def test_counter_service_increment(counter_service):
    """Increment taken and printed, verify counts."""
    counter_service.increment_taken()
    counter_service.increment_taken()
    counter_service.increment_printed()

    c = counter_service.counters
    assert c["total_taken"] == 2
    assert c["session_taken"] == 2
    assert c["total_printed"] == 1
    assert c["session_printed"] == 1


def test_counter_service_persistence(tmp_path):
    """Save counters, create a new instance, verify loaded values."""
    svc1 = CounterService(data_dir=str(tmp_path))
    svc1.increment_taken()
    svc1.increment_taken()
    svc1.increment_taken()
    svc1.increment_printed()

    # Create new instance from same data dir
    svc2 = CounterService(data_dir=str(tmp_path))
    c = svc2.counters
    assert c["total_taken"] == 3
    assert c["total_printed"] == 1


def test_counter_service_reset_session(counter_service):
    """Reset session preserves totals."""
    counter_service.increment_taken()
    counter_service.increment_taken()
    counter_service.increment_printed()

    counter_service.reset_session()

    c = counter_service.counters
    assert c["total_taken"] == 2
    assert c["total_printed"] == 1
    assert c["session_taken"] == 0
    assert c["session_printed"] == 0


def test_counter_service_initial_state(counter_service):
    """Fresh counter service starts at zero."""
    c = counter_service.counters
    assert c["total_taken"] == 0
    assert c["total_printed"] == 0
    assert c["session_taken"] == 0
    assert c["session_printed"] == 0
    assert "session_start" in c
