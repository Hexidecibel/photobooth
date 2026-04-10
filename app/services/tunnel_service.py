"""Tunnel service for exposing the photobooth to the internet.

Manages a configurable tunnel subprocess (cush-tools, cloudflared, ngrok, etc.)
and derives the public URL from the configured pattern.
"""

import asyncio
import logging
import shlex
import subprocess

from app.models.config_schema import NetworkConfig

logger = logging.getLogger(__name__)


class TunnelService:
    def __init__(self, config: NetworkConfig, port: int):
        self._config = config
        self._port = port
        self._process: subprocess.Popen | None = None
        self._public_url: str | None = None
        self._running = False
        self._monitor_task: asyncio.Task | None = None

    async def start(self) -> str | None:
        """Start the tunnel and return the public URL."""
        if not self._config.tunnel_enabled or not self._config.tunnel_command:
            return None

        cmd = self._config.tunnel_command.format(
            port=self._port,
            name=self._config.tunnel_name,
        )

        logger.info(f"Starting tunnel: {cmd}")

        try:
            self._process = await asyncio.to_thread(
                subprocess.Popen,
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Give it a moment to start
            await asyncio.sleep(2)

            # Check if it's still running
            if self._process.poll() is not None:
                stderr = (
                    self._process.stderr.read().decode()
                    if self._process.stderr
                    else ""
                )
                logger.error(f"Tunnel failed to start: {stderr}")
                return None

            # Derive the public URL from the pattern
            self._public_url = self._config.tunnel_url_pattern.format(
                name=self._config.tunnel_name,
            )

            logger.info(f"Tunnel active: {self._public_url}")

            # Start monitoring for tunnel restarts
            if not self._running:
                self._running = True
                self._monitor_task = asyncio.create_task(self._monitor())

            return self._public_url

        except Exception as e:
            logger.error(f"Tunnel start failed: {e}")
            return None

    async def _monitor(self):
        """Monitor tunnel process and restart if it dies."""
        while self._running:
            await asyncio.sleep(5)
            if self._process and self._process.poll() is not None:
                logger.warning("Tunnel died, restarting...")
                self._process = None
                await self.start()

    @property
    def public_url(self) -> str | None:
        return self._public_url

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    async def stop(self):
        """Stop the tunnel subprocess."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        if self._process:
            self._process.terminate()
            try:
                await asyncio.to_thread(self._process.wait, timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            self._public_url = None
            logger.info("Tunnel stopped")
