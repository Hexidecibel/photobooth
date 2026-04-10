"""Tests for the built-in plugins."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.config_schema import AppConfig
from app.models.state import BoothState, CaptureSession
from app.plugins.builtin.camera_plugin import CameraPlugin
from app.plugins.builtin.picture_plugin import PicturePlugin
from app.plugins.builtin.view_plugin import ViewPlugin


@pytest.fixture
def config():
    return AppConfig()


@pytest.fixture
def broadcast():
    return AsyncMock()


@pytest.fixture
def session():
    return CaptureSession(capture_count=4)


# --- ViewPlugin tests ---


class TestViewPlugin:
    @pytest.fixture
    def plugin(self, config, broadcast):
        vp = ViewPlugin(config, broadcast)
        # Provide a mock state machine so _on_choose_do can create sessions
        sm = MagicMock()
        sm.new_session = MagicMock(return_value=CaptureSession())
        vp._sm = sm
        return vp

    @pytest.mark.asyncio
    async def test_idle_start(self, plugin, session):
        result = await plugin._on_idle_do(session, event="start")
        assert result == BoothState.CHOOSE

    @pytest.mark.asyncio
    async def test_idle_no_event(self, plugin, session):
        result = await plugin._on_idle_do(session, event=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_choose_cancel(self, plugin, session):
        result = await plugin._on_choose_do(session, event="cancel")
        assert result == BoothState.IDLE

    @pytest.mark.asyncio
    async def test_choose_option(self, plugin, session):
        result = await plugin._on_choose_do(
            session, event="choose", mode="photo", template="lets-go"
        )
        assert result == BoothState.PREVIEW
        plugin._sm.new_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_retake(self, plugin):
        session = CaptureSession(capture_count=4)
        session.captures.append(Path("/fake/img.jpg"))
        session.composite_path = Path("/fake/composite.jpg")

        result = await plugin._on_review_do(session, event="retake")
        assert result == BoothState.PREVIEW
        assert len(session.captures) == 0
        assert session.composite_path is None

    @pytest.mark.asyncio
    async def test_review_print(self, plugin, session):
        result = await plugin._on_review_do(session, event="print")
        assert result == BoothState.PRINT

    @pytest.mark.asyncio
    async def test_review_done(self, plugin, session):
        result = await plugin._on_review_do(session, event="done")
        assert result == BoothState.THANKYOU

    @pytest.mark.asyncio
    async def test_review_select_effect(self, plugin, session):
        result = await plugin._on_review_do(
            session, event="select_effect", effect="sepia"
        )
        assert result is None
        assert session.selected_effect == "sepia"

    @pytest.mark.asyncio
    async def test_print_done(self, plugin, session):
        result = await plugin._on_print_do(session, event="print_complete")
        assert result == BoothState.THANKYOU

    @pytest.mark.asyncio
    async def test_thankyou_auto_idle(self, plugin, session):
        result = await plugin._on_thankyou_do(session, event="auto_idle")
        assert result == BoothState.IDLE

    @pytest.mark.asyncio
    async def test_thankyou_start(self, plugin, session):
        result = await plugin._on_thankyou_do(session, event="start")
        assert result == BoothState.IDLE


# --- CameraPlugin tests ---


class TestCameraPlugin:
    @pytest.mark.asyncio
    async def test_capture(self, config, broadcast, tmp_path):
        mock_camera = AsyncMock()
        saved_path = tmp_path / "capture_000.jpg"
        mock_camera.capture_still.return_value = saved_path

        plugin = CameraPlugin(mock_camera, config, broadcast)
        session = CaptureSession(capture_count=4)

        await plugin._on_capture_enter(session=session)

        mock_camera.capture_still.assert_awaited_once()
        assert len(session.captures) == 1
        assert session.captures[0] == saved_path
        # Check broadcast was called with flash and capture_complete
        calls = [c.args[0] for c in broadcast.call_args_list]
        assert any(m["type"] == "flash" for m in calls)
        assert any(m["type"] == "capture_complete" for m in calls)

    @pytest.mark.asyncio
    async def test_multi_capture_needs_more(self, config, broadcast):
        mock_camera = AsyncMock()
        plugin = CameraPlugin(mock_camera, config, broadcast)

        session = CaptureSession(capture_count=3)
        session.captures.append(Path("/fake/1.jpg"))  # 1 of 3

        result = await plugin._on_capture_do(
            session=session, event="enter_complete"
        )
        assert result == BoothState.PREVIEW

    @pytest.mark.asyncio
    async def test_multi_capture_all_done(self, config, broadcast):
        mock_camera = AsyncMock()
        plugin = CameraPlugin(mock_camera, config, broadcast)

        session = CaptureSession(capture_count=2)
        session.captures.append(Path("/fake/1.jpg"))
        session.captures.append(Path("/fake/2.jpg"))

        result = await plugin._on_capture_do(
            session=session, event="enter_complete"
        )
        assert result == BoothState.PROCESSING

    @pytest.mark.asyncio
    async def test_preview_countdown_complete(self, config, broadcast):
        mock_camera = AsyncMock()
        plugin = CameraPlugin(mock_camera, config, broadcast)
        session = CaptureSession()

        result = await plugin._on_preview_do(
            session=session, event="countdown_complete"
        )
        assert result == BoothState.CAPTURE

    @pytest.mark.asyncio
    async def test_preview_cancel(self, config, broadcast):
        mock_camera = AsyncMock()
        plugin = CameraPlugin(mock_camera, config, broadcast)
        session = CaptureSession()

        result = await plugin._on_preview_do(session=session, event="cancel")
        assert result == BoothState.IDLE


# --- PicturePlugin tests ---


class TestPicturePlugin:
    @pytest.mark.asyncio
    async def test_processing(self, config, broadcast):
        plugin = PicturePlugin(config, broadcast)

        mock_pipeline = AsyncMock()
        mock_pipeline.process.return_value = Path("/fake/output.jpg")
        plugin._pipeline = mock_pipeline

        session = CaptureSession(capture_count=1)
        session.captures.append(Path("/fake/1.jpg"))

        await plugin._on_processing_enter(session=session)

        mock_pipeline.process.assert_awaited_once()
        # Verify progress and result broadcasts
        calls = [c.args[0] for c in broadcast.call_args_list]
        types = [m["type"] for m in calls]
        assert "processing_progress" in types
        assert "result_ready" in types

    @pytest.mark.asyncio
    async def test_processing_do_with_composite(self, config, broadcast):
        plugin = PicturePlugin(config, broadcast)
        session = CaptureSession()
        session.composite_path = Path("/fake/composite.jpg")

        result = await plugin._on_processing_do(session=session)
        assert result == BoothState.REVIEW

    @pytest.mark.asyncio
    async def test_processing_do_without_composite(self, config, broadcast):
        plugin = PicturePlugin(config, broadcast)
        session = CaptureSession()

        result = await plugin._on_processing_do(session=session)
        assert result is None
