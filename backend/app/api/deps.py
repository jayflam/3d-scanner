"""FastAPI dependency injection for DB sessions and services."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.services.blob_storage import blob_storage, BlobStorageService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, auto-commit on success, rollback on error."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_blob_storage() -> BlobStorageService:
    """Return the blob storage singleton."""
    return blob_storage
