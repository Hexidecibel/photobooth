"""FastAPI dependency injection functions."""

from fastapi import HTTPException, Request

from app.camera.base import CameraBase
from app.hardware.printer import PrinterService
from app.models.config_schema import AppConfig
from app.services.state_machine import StateMachine


def get_camera(request: Request) -> CameraBase:
    """Return the camera instance from app state."""
    camera = request.app.state.camera
    if camera is None:
        raise HTTPException(status_code=503, detail="No camera available")
    return camera


def get_state_machine(request: Request) -> StateMachine:
    """Return the state machine from app state."""
    return request.app.state.state_machine


def get_config(request: Request) -> AppConfig:
    """Return the app config from app state."""
    return request.app.state.config


def get_printer(request: Request) -> PrinterService:
    """Return the printer service from app state."""
    printer = request.app.state.printer
    if printer is None:
        raise HTTPException(status_code=503, detail="Printer not available")
    return printer
