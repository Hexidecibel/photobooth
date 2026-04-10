"""Tunnel service — localhost.run SSH tunnel for public QR code access."""

import asyncio
import logging
import re
import subprocess

from app.models.config_schema import NetworkConfig

logger = logging.getLogger(__name__)


class TunnelService:
    """Manages a localhost.run SSH tunnel."""

    def __init__(self, config: NetworkConfig, port: int):
        self._config = config
        self._port = port
        self._process: subprocess.Popen | None = None
        self._public_url: str | None = None
        self._monitor_task: asyncio.Task | None = None

    @property
    def public_url(self) -> str | None:
        return self._public_url

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    async def start(self) -> str | None:
        if not self._config.tunnel_enabled:
            return None

        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-R", f"80:localhost:{self._port}",
            "nokey@localhost.run",
        ]

        logger.info("Starting localhost.run tunnel for port %s", self._port)

        try:
            self._process = await asyncio.to_thread(
                subprocess.Popen,
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            url = await self._read_url(timeout=15)

            if url:
                self._public_url = url
                logger.info("Tunnel active: %s", url)
                self._start_monitor()
                return url

            logger.error("Failed to get URL from localhost.run")
            await self.stop()
            return None

        except FileNotFoundError:
            logger.error("SSH not found")
            return None
        except Exception as e:
            logger.error("Tunnel failed: %s", e)
            return None

    async def _read_url(self, timeout: int = 15) -> str | None:
        async def _read():
            if not self._process or not self._process.stdout:
                return None
            while True:
                line = await asyncio.to_thread(self._process.stdout.readline)
                if not line:
                    break
                line = line.strip()
                match = re.search(
                    r"(https://[a-zA-Z0-9-]+\.lhr\.life)", line
                )
                if match:
                    return match.group(1)
            return None

        try:
            return await asyncio.wait_for(_read(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def _start_monitor(self):
        if self._monitor_task and not self._monitor_task.done():
            return
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        while True:
            await asyncio.sleep(10)
            if self._process and self._process.poll() is not None:
                logger.warning("Tunnel died, restarting...")
                self._process = None
                self._public_url = None
                await self.start()
                break

    async def stop(self):
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
