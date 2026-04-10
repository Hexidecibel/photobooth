import logging
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from app.models.config_schema import SharingConfig
from app.models.state import CaptureSession

logger = logging.getLogger(__name__)


class ShareService:
    def __init__(self, config: SharingConfig, data_dir: str = "data"):
        self._config = config
        self._db_path = Path(data_dir) / "gallery.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS photos (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    photo_path TEXT NOT NULL,
                    share_token TEXT UNIQUE,
                    event_name TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_share_token
                ON photos(share_token)
            """)
            conn.commit()

    def create_share(self, session: CaptureSession) -> str:
        """Create a share token for a photo session."""
        token = secrets.token_urlsafe(6)  # ~8 chars

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO photos
                   (id, session_id, photo_path, share_token, event_name, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.id,
                    str(session.composite_path) if session.composite_path else "",
                    token,
                    self._config.event_name,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

        session.share_token = token
        return token

    def get_by_token(self, token: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM photos WHERE share_token = ?", (token,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_id(self, photo_id: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM photos WHERE id = ?", (photo_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_photos(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM photos ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_photo(self, photo_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM photos WHERE id = ?", (photo_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def generate_qr_png(self, url: str, size: int = 200) -> bytes:
        """Generate QR code as PNG bytes."""
        try:
            from io import BytesIO

            import qrcode

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            # Resize
            img = img.resize((size, size))
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except ImportError:
            # Fallback: return a simple placeholder
            logger.warning("qrcode library not installed, QR codes disabled")
            return b""

    def get_share_url(self, token: str) -> str:
        if self._config.base_url:
            base = self._config.base_url.rstrip("/")
            return f"{base}/share/{token}"
        return f"/share/{token}"
