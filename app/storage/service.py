import base64
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text

from app.database.models.media import MediaFile

logger = logging.getLogger(__name__)


class StoragePoolService:
    """
    SHIV Native Media & Blob Storage Engine.
    Stores and serves files directly via persistent database storage with zero external dependencies,
    zero cloud fees, and no credit card required.
    """

    async def _ensure_table(self, db: AsyncSession):
        """Creates the media_files table on-the-fly if it doesn't already exist."""
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS media_files (
                    id VARCHAR(36) PRIMARY KEY,
                    project_id VARCHAR(36) NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    content_type VARCHAR(100) NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    data_base64 TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await db.execute(text("CREATE INDEX IF NOT EXISTS ix_media_files_project_id ON media_files (project_id)"))
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning(f"Failed to auto-create media_files table: {e}")

    async def upload_file(
        self,
        db: AsyncSession,
        project_id: str,
        file_name: str,
        file_bytes: bytes,
        content_type: str,
        base_url: str = ""
    ) -> Dict[str, Any]:
        """
        Uploads and persists a file to the database.
        Returns a permanent public URL and file metadata.
        """
        data_b64 = base64.b64encode(file_bytes).decode('ascii')
        size_bytes = len(file_bytes)
        safe_content_type = content_type or "application/octet-stream"

        media_record = MediaFile(
            project_id=project_id,
            file_name=file_name,
            content_type=safe_content_type,
            size_bytes=size_bytes,
            data_base64=data_b64,
        )

        try:
            db.add(media_record)
            await db.commit()
            await db.refresh(media_record)
        except Exception as e:
            await db.rollback()
            if "media_files" in str(e).lower():
                await self._ensure_table(db)
                db.add(media_record)
                await db.commit()
                await db.refresh(media_record)
            else:
                raise

        clean_base = base_url.rstrip("/") if base_url else ""
        file_url = f"{clean_base}/storage/file/{media_record.id}"

        logger.info(f"[StorageEngine] Persisted {file_name} ({size_bytes} bytes) for project {project_id} -> {file_url}")

        return {
            "id": media_record.id,
            "file_name": media_record.file_name,
            "url": file_url,
            "content_type": media_record.content_type,
            "size": media_record.size_bytes,
            "created_at": media_record.created_at.isoformat() if media_record.created_at else None,
        }

    async def get_file(self, db: AsyncSession, file_id: str) -> Optional[Tuple[bytes, str, str]]:
        """
        Fetches a file record by ID and decodes the binary content.
        Returns (file_bytes, content_type, file_name) or None if not found.
        """
        try:
            stmt = select(MediaFile).where(MediaFile.id == file_id)
            res = await db.execute(stmt)
            record = res.scalar_one_or_none()
        except Exception as e:
            await db.rollback()
            if "media_files" in str(e).lower():
                await self._ensure_table(db)
                return None
            raise

        if not record:
            return None

        try:
            file_bytes = base64.b64decode(record.data_base64.encode('ascii'))
            return file_bytes, record.content_type, record.file_name
        except Exception as e:
            logger.error(f"Failed to decode file {file_id}: {e}")
            return None

    async def list_files(
        self,
        db: AsyncSession,
        project_id: str,
        base_url: str = "",
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lists stored files for a specific project.
        """
        try:
            stmt = (
                select(MediaFile)
                .where(MediaFile.project_id == project_id)
                .order_by(MediaFile.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            res = await db.execute(stmt)
            records = res.scalars().all()
        except Exception as e:
            await db.rollback()
            if "media_files" in str(e).lower():
                await self._ensure_table(db)
                return []
            raise

        clean_base = base_url.rstrip("/") if base_url else ""
        return [
            {
                "id": r.id,
                "file_name": r.file_name,
                "url": f"{clean_base}/storage/file/{r.id}",
                "content_type": r.content_type,
                "size": r.size_bytes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    async def delete_file(self, db: AsyncSession, file_id: str, project_id: Optional[str] = None) -> bool:
        """
        Deletes a stored file by ID.
        """
        try:
            stmt = select(MediaFile).where(MediaFile.id == file_id)
            if project_id:
                stmt = stmt.where(MediaFile.project_id == project_id)

            res = await db.execute(stmt)
            record = res.scalar_one_or_none()
            if not record:
                return False

            await db.delete(record)
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            if "media_files" in str(e).lower():
                await self._ensure_table(db)
                return False
            raise
