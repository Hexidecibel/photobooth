import logging
import re
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
            # Albums table for local event management
            conn.execute("""
                CREATE TABLE IF NOT EXISTS albums (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE,
                    cloud_gallery_id TEXT,
                    created_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0
                )
            """)
            # Add album_id column to photos (migration-safe)
            try:
                conn.execute(
                    "ALTER TABLE photos ADD COLUMN album_id TEXT DEFAULT ''"
                )
            except Exception:
                pass  # Column already exists
            conn.commit()

    def create_share(self, session: CaptureSession, album_id: str = "") -> str:
        """Create a share token for a photo session."""
        token = secrets.token_urlsafe(6)  # ~8 chars

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO photos
                   (id, session_id, photo_path, share_token, event_name,
                    created_at, album_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.id,
                    str(session.composite_path) if session.composite_path else "",
                    token,
                    self._config.event_name,
                    datetime.now().isoformat(),
                    album_id,
                ),
            )
            conn.commit()

        session.share_token = token
        return token

    def create_share_token(self, photo_id: str) -> str | None:
        """Create a share token for an existing photo that doesn't have one."""
        token = secrets.token_urlsafe(6)
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT id FROM photos WHERE id = ?", (photo_id,)
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE photos SET share_token = ?"
                " WHERE id = ? AND share_token IS NULL",
                (token, photo_id),
            )
            conn.commit()
            # Return the actual token (might already have one)
            conn.row_factory = sqlite3.Row
            updated = conn.execute(
                "SELECT share_token FROM photos WHERE id = ?", (photo_id,)
            ).fetchone()
            return dict(updated)["share_token"] if updated else token

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

    # ── Album / Event CRUD ───────────────────────────────────────

    def create_album(
        self, name: str, slug: str = "", cloud_gallery_id: str = "",
    ) -> dict:
        """Create a new album/event."""
        album_id = secrets.token_hex(6)
        if not slug:
            slug = name.lower().replace(" ", "-").replace("'", "")
            slug = re.sub(r"[^a-z0-9-]", "", slug)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO albums
                   (id, name, slug, cloud_gallery_id, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (
                    album_id, name, slug,
                    cloud_gallery_id, datetime.now().isoformat(),
                ),
            )
            conn.commit()
        return {
            "id": album_id, "name": name, "slug": slug,
            "cloud_gallery_id": cloud_gallery_id,
        }

    def list_albums(self) -> list[dict]:
        """List all albums with photo counts."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM albums ORDER BY created_at DESC",
            ).fetchall()
            result = []
            for row in rows:
                album = dict(row)
                count = conn.execute(
                    "SELECT COUNT(*) FROM photos WHERE album_id = ?",
                    (album["id"],),
                ).fetchone()[0]
                album["photo_count"] = count
                result.append(album)
            return result

    def get_active_album(self) -> dict | None:
        """Get the currently active album."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM albums WHERE is_active = 1 LIMIT 1",
            ).fetchone()
            return dict(row) if row else None

    def activate_album(self, album_id: str) -> bool:
        """Set an album as active (deactivate all others)."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("UPDATE albums SET is_active = 0")
            conn.execute(
                "UPDATE albums SET is_active = 1 WHERE id = ?", (album_id,),
            )
            conn.commit()
        return True

    def delete_album(self, album_id: str) -> bool:
        """Delete an album (photos stay, just lose the album tag)."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE photos SET album_id = '' WHERE album_id = ?",
                (album_id,),
            )
            conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
            conn.commit()
        return True

    def get_album_photos(
        self, album_id: str, limit: int = 100, offset: int = 0,
    ) -> list[dict]:
        """Get photos for a specific album."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM photos WHERE album_id = ?"
                " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (album_id, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

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
