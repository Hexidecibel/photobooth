"""Tunnel service for exposing the photobooth to the internet.

Supports localhost.run (zero-dependency SSH tunnel) and custom commands
for self-hosted tunnels (cush-tools, ngrok, frp, etc.).
"""

import asyncio
import logging
import re
import shlex
import subprocess

from app.models.config_schema import NetworkConfig

logger = logging.getLogger(__name__)


class TunnelService:
    """Manages a tunnel to expose the booth to the internet."""

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
        """Start the tunnel and return the public URL."""
        if not self._config.tunnel_enabled:
            return None

        provider = self._config.tunnel_provider

        if provider == "localhost.run":
            return await self._start_localhost_run()
        elif provider == "custom":
            return await self._start_custom()
        else:
            logger.error(f"Unknown tunnel provider: {provider}")
            return None

    async def _start_localhost_run(self) -> str | None:
        """Start a tunnel via localhost.run (SSH-based, zero install)."""
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-R", f"80:localhost:{self._port}",
            "nokey@localhost.run",
        ]

        logger.info(f"Starting localhost.run tunnel for port {self._port}")

        try:
            self._process = await asyncio.to_thread(
                subprocess.Popen,
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # localhost.run prints the URL to stdout
            # Read lines until we find the URL (looks like https://xxxxx.lhr.life)
            url = await self._read_url_from_output(
                pattern=r"(https://[a-zA-Z0-9-]+\.lhr\.life)",
                timeout=15,
            )

            if url:
                self._public_url = url
                logger.info(f"localhost.run tunnel active: {url}")
                self._start_monitor()
                return url
            else:
                logger.error("Failed to get URL from localhost.run")
                await self.stop()
                return None

        except FileNotFoundError:
            logger.error("SSH not found — localhost.run requires ssh")
            return None
        except Exception as e:
            logger.error(f"localhost.run tunnel failed: {e}")
            return None

    async def _start_custom(self) -> str | None:
        """Start a tunnel using a custom command."""
        if not self._config.tunnel_custom_command:
            logger.error("Custom tunnel command is empty")
            return None

        cmd = self._config.tunnel_custom_command.format(
            port=self._port,
            name=self._config.tunnel_name,
        )

        logger.info(f"Starting custom tunnel: {cmd}")

        try:
            self._process = await asyncio.to_thread(
                subprocess.Popen,
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Give it a moment to start
            await asyncio.sleep(3)

            if self._process.poll() is not None:
                output = self._process.stdout.read() if self._process.stdout else ""
                logger.error(f"Custom tunnel failed to start: {output}")
                return None

            # Derive URL from pattern
            self._public_url = self._config.tunnel_url_pattern.format(
                name=self._config.tunnel_name,
            )

            logger.info(f"Custom tunnel active: {self._public_url}")
            self._start_monitor()
            return self._public_url

        except Exception as e:
            logger.error(f"Custom tunnel failed: {e}")
            return None

    async def _read_url_from_output(
        self, pattern: str, timeout: int = 15
    ) -> str | None:
        """Read process output and extract URL matching pattern."""

        async def _read():
            if not self._process or not self._process.stdout:
                return None
            while True:
                line = await asyncio.to_thread(self._process.stdout.readline)
                if not line:
                    break
                line = line.strip()
                logger.debug(f"Tunnel output: {line}")
                match = re.search(pattern, line)
                if match:
                    return match.group(1)
            return None

        try:
            return await asyncio.wait_for(_read(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for tunnel URL ({timeout}s)")
            return None

    def _start_monitor(self):
        """Start background task to monitor and restart tunnel if it dies."""
        if self._monitor_task and not self._monitor_task.done():
            return
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Monitor tunnel process and restart if it dies."""
        while True:
            await asyncio.sleep(10)
            if self._process and self._process.poll() is not None:
                logger.warning("Tunnel died, restarting...")
                self._process = None
                self._public_url = None
                await self.start()
                if not self._public_url:
                    logger.error("Tunnel restart failed")
                break  # New start() creates its own monitor

    async def stop(self):
        """Stop the tunnel."""
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
