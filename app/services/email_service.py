import asyncio
import logging
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.models.config_schema import EmailConfig

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, config: EmailConfig):
        self._config = config

    @property
    def is_available(self) -> bool:
        return (
            self._config.enabled
            and bool(self._config.smtp_host)
            and bool(self._config.from_address)
        )

    async def send_photo(
        self,
        to_email: str,
        photo_path: Path,
        event_name: str = "",
        share_url: str = "",
    ) -> bool:
        if not self.is_available:
            return False
        try:
            return await asyncio.to_thread(
                self._send, to_email, photo_path, event_name, share_url
            )
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def _send(
        self,
        to_email: str,
        photo_path: Path,
        event_name: str,
        share_url: str,
    ) -> bool:
        msg = MIMEMultipart()
        msg["From"] = f"{self._config.from_name} <{self._config.from_address}>"
        msg["To"] = to_email
        msg["Subject"] = self._config.subject

        body = self._config.body_template.format(
            event_name=event_name,
            share_url=share_url,
        )
        msg.attach(MIMEText(body, "plain"))

        # Attach photo
        with open(photo_path, "rb") as f:
            img = MIMEImage(f.read(), name="photobooth.jpg")
            msg.attach(img)

        with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
            server.starttls()
            if self._config.smtp_user:
                server.login(self._config.smtp_user, self._config.smtp_password)
            server.send_message(msg)

        return True
