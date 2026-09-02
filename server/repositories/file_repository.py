"""
File Repository: Persistence adapter for raw assets, markdown, and audio/video files.
"""

import os
import uuid
import time
import aiofiles
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile
from server.core.config import config
from server.core.exceptions import ResourceNotFoundException

class FileRepository:
    def __init__(self):
        self.uploads_dir = config.uploads_dir
        self.output_dir = config.output_dir

    async def save_uploaded_video(self, upload_file: UploadFile, filename: str) -> Tuple[str, str, str]:
        """Saves video, computes SHA-256, and returns (filename, path, hash)."""
        import asyncio
        import hashlib
        asyncio.create_task(self._cleanup_old_files())
        
        ext = os.path.splitext(filename)[1]
        unique_name = f"video_{uuid.uuid4().hex}{ext}"
        filepath = self.uploads_dir / filename
        
        hasher = hashlib.sha256()

        async with aiofiles.open(filepath, "wb") as f:
            while chunk := await upload_file.read(1024 * 1024):
                await f.write(chunk)
                hasher.update(chunk)

        return filename, str(filepath), hasher.hexdigest()

    async def save_uploaded_readme(self, content_bytes: bytes, original_filename: str) -> Tuple[str, str, str]:
        """Saves a uploaded README markdown file to uploads/."""
        filename = f"readme_{uuid.uuid4().hex[:8]}.md"
        filepath = self.uploads_dir / filename
        text = content_bytes.decode("utf-8", errors="replace")

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(text)

        return filename, text, str(filepath)

    def get_upload_path(self, filename: str) -> str:
        """Resolves an upload path and verifies existence."""
        path = self.uploads_dir / filename
        if not path.exists():
            raise ResourceNotFoundException(message=f"Uploaded file '{filename}' does not exist on disk.")
        return str(path)

    def get_output_path(self, filename: str) -> str:
        """Resolves an output path."""
        return str(self.output_dir / filename)

    def save_output_file(self, filename: str, content: bytes) -> str:
        """Synchronously writes a binary artifact to output/."""
        path = self.output_dir / filename
        with open(path, "wb") as f:
            f.write(content)
        return str(path)

    async def _cleanup_old_files(self):
        """Deletes video and output files older than 24 hours to manage storage."""
        cutoff_time = time.time() - (24 * 3600)
        
        for directory in [self.uploads_dir, self.output_dir]:
            try:
                for file_path in directory.iterdir():
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink(missing_ok=True)
            except Exception as e:
                pass # Fail silently on cleanup errors

file_repository = FileRepository()
