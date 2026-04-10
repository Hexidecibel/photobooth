"""Tests for the hardware abstraction layer (GPIO + printer)."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.config_schema import AppConfig, ControlsConfig, PrinterConfig
from app.models.state import BoothState


@pytest.fixture
def controls_config():
    return ControlsConfig()


@pytest.fixture
def printer_config():
    return PrinterConfig(enabled=True, printer_name="test-printer")


@pytest.fixture
def app_config():
    return AppConfig()


@pytest.fixture
def mock_state_machine():
    sm = MagicMock()
    sm.state = BoothState.IDLE
    sm.trigger = AsyncMock()
    return sm


# --- GPIO tests ---


def test_gpio_controller_no_gpiozero(controls_config, mock_state_machine):
    """GPIOController handles missing gpiozero gracefully."""
    with patch.dict(sys.modules, {"gpiozero": None}):
        # Force re-import so _setup hits the ImportError path
        from importlib import reload

        import app.hardware.gpio as gpio_mod

        reload(gpio_mod)

        gpio = gpio_mod.GPIOController(
            controls_config,
            state_machine=mock_state_machine,
            broadcast=AsyncMock(),
        )
        # Should have no hardware attached
        assert gpio._capture_btn is None
        assert gpio._print_btn is None
        assert gpio._capture_led is None
        assert gpio._print_led is None


def test_gpio_set_state_leds_without_hardware(controls_config, mock_state_machine):
    """set_state_leds does not crash when LEDs are None."""
    with patch.dict(sys.modules, {"gpiozero": None}):
        from importlib import reload

        import app.hardware.gpio as gpio_mod

        reload(gpio_mod)

        gpio = gpio_mod.GPIOController(
            controls_config,
            state_machine=mock_state_machine,
            broadcast=AsyncMock(),
        )
        # Should not raise for any state
        for state in BoothState:
            gpio.set_state_leds(state)


# --- Printer tests ---


def test_printer_service_no_cups(printer_config):
    """PrinterService handles missing cups gracefully."""
    with patch.dict(sys.modules, {"cups": None}):
        from importlib import reload

        import app.hardware.printer as printer_mod

        reload(printer_mod)

        printer = printer_mod.PrinterService(printer_config)
        assert printer._conn is None
        assert printer._printer_name is None


def test_printer_not_available(printer_config):
    """is_available returns False when no connection exists."""
    with patch.dict(sys.modules, {"cups": None}):
        from importlib import reload

        import app.hardware.printer as printer_mod

        reload(printer_mod)

        printer = printer_mod.PrinterService(printer_config)
        assert printer.is_available is False


# --- Factory tests ---


def test_setup_gpio_returns_none_on_failure(app_config, mock_state_machine):
    """setup_gpio returns None when GPIO init fails."""
    from app.hardware.factory import setup_gpio

    with patch(
        "app.hardware.factory.GPIOController",
        side_effect=RuntimeError("no GPIO"),
    ):
        result = setup_gpio(app_config, mock_state_machine, AsyncMock())
        assert result is None


def test_setup_printer_disabled():
    """setup_printer returns None when printer is disabled in config."""
    from app.hardware.factory import setup_printer

    config = AppConfig(printer=PrinterConfig(enabled=False))
    result = setup_printer(config)
    assert result is None
