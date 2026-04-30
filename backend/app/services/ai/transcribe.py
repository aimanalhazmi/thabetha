from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_TYPES: dict[str, str] = {
    "audio/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
}

ALLOWED_EXTENSIONS = {".webm", ".mp3", ".wav", ".m4a"}


@dataclass(frozen=True)
class TranscriptionResult:
    raw_transcript: str
    language_hint: str | None = None


class TranscriptionProvider:
    async def transcribe(self, *, content: bytes, file_name: str, content_type: str | None) -> TranscriptionResult:
        raise NotImplementedError


class OpenAITranscriptionProvider(TranscriptionProvider):
    async def transcribe(self, *, content: bytes, file_name: str, content_type: str | None) -> TranscriptionResult:
        settings = get_settings()
        url = f"{settings.openai_base_url.rstrip('/')}/audio/transcriptions"
        headers: dict[str, str] = {}
        if settings.openai_api_key:
            headers["Authorization"] = f"Bearer {settings.openai_api_key}"
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                files = {
                    "file": (file_name, content, content_type or "audio/mpeg")
                }
                payload = {
                    "model": settings.openai_transcription_model,
                    "response_format": "json",
                }
                response = await client.post(url, headers=headers, data=payload, files=files)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            logger.warning("Transcription upstream %s returned %s: %s", url, exc.response.status_code, body)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "transcription_failed", "message": "Could not transcribe the audio"},
            ) from exc
        except Exception as exc:
            logger.warning("Transcription upstream %s failed: %r", url, exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "transcription_failed", "message": "Could not transcribe the audio"},
            ) from exc
        text = str(data.get("text") or "").strip()
        if not text:
            logger.warning("Transcription upstream %s returned empty text: %s", url, str(data)[:500])
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "transcription_failed", "message": "Could not transcribe the audio"},
            )
        return TranscriptionResult(raw_transcript=text, language_hint=data.get("language"))


def validate_audio_input(*, file_name: str, content_type: str | None, client_duration_seconds: float | None) -> None:
    settings = get_settings()
    lower_name = file_name.lower()
    has_allowed_ext = any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS)
    base_content_type = content_type.split(";", 1)[0].strip().lower() if content_type else None
    has_allowed_type = base_content_type in ALLOWED_AUDIO_TYPES if base_content_type else False
    if not has_allowed_ext and not has_allowed_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"code": "unsupported_audio_type", "message": "Unsupported audio format"},
        )
    if client_duration_seconds is not None and client_duration_seconds > settings.ai_voice_max_duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "audio_too_long", "message": "Voice notes must be 60 seconds or shorter"},
        )


def get_transcription_provider() -> TranscriptionProvider:
    settings = get_settings()
    if settings.ai_transcription_provider == "openai":
        return OpenAITranscriptionProvider()
    from app.services.ai.mock_transcribe import MockTranscriptionProvider

    return MockTranscriptionProvider()
