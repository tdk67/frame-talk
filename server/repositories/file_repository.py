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

    async def save_uploaded_video(self, upload_file: UploadFile, original_filename: str) -> Tuple[str, str, str]:
        """Saves video, enforces size limits, computes SHA-256, and returns (filename, path, hash)."""
        import asyncio
        import hashlib
        from server.core.exceptions import InvalidInputException
        asyncio.create_task(self._cleanup_old_files())

        ext = os.path.splitext(os.path.basename(original_filename))[1].lower()
        if ext not in config.supported_video_extensions:
            raise InvalidInputException(
                f"Unsupported video format '{ext}'. Allowed formats: {', '.join(config.supported_video_extensions)}"
            )

        unique_name = f"video_{uuid.uuid4().hex[:12]}{ext}"
        filepath = self.uploads_dir / unique_name

        max_bytes = int(config.max_video_size_mb * 1024 * 1024)
        total_bytes = 0
        hasher = hashlib.sha256()

        async with aiofiles.open(filepath, "wb") as f:
            while chunk := await upload_file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    await f.close()
                    filepath.unlink(missing_ok=True)
                    raise InvalidInputException(f"Video file exceeds maximum limit of {config.max_video_size_mb:.0f}MB.")
                await f.write(chunk)
                hasher.update(chunk)

        return unique_name, str(filepath), hasher.hexdigest()

    async def save_uploaded_readme(self, content_bytes: bytes, original_filename: str) -> Tuple[str, str, str]:
        """Saves a uploaded README markdown file to uploads/ with injection inspection."""
        from server.core.guardrails import sanitize_and_inspect_text
        filename = f"readme_{uuid.uuid4().hex[:8]}.md"
        filepath = self.uploads_dir / filename
        text = content_bytes.decode("utf-8", errors="replace")
        
        # Scan for prompt injection and sanitize
        sanitized_text = sanitize_and_inspect_text(text, max_chars=50000, context_name="Uploaded Documentation")

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(sanitized_text)

        return filename, sanitized_text, str(filepath)

    def _safe_resolve(self, directory: Path, filename: str) -> Path:
        """Sanitizes filename and prevents directory traversal attacks."""
        import re
        from server.core.exceptions import InvalidInputException
        cleaned = filename.strip()
        if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
            raise InvalidInputException(f"Path traversal characters detected in '{filename}'.")
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", cleaned):
            raise InvalidInputException("Invalid filename characters detected.")
        resolved = (directory / cleaned).resolve()
        if not resolved.is_relative_to(directory.resolve()):
            raise InvalidInputException("Path traversal attempt detected.")
        return resolved

    def get_upload_path(self, filename: str) -> str:
        """Resolves an upload path safely and verifies existence."""
        path = self._safe_resolve(self.uploads_dir, filename)
        if not path.exists():
            raise ResourceNotFoundException(message=f"Uploaded file '{filename}' does not exist on disk.")
        return str(path)

    def get_output_path(self, filename: str) -> str:
        """Resolves an output path safely."""
        path = self._safe_resolve(self.output_dir, filename)
        return str(path)

    def save_output_file(self, filename: str, content: bytes) -> str:
        """Synchronously writes a binary artifact to output/ safely."""
        path = self._safe_resolve(self.output_dir, filename)
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
