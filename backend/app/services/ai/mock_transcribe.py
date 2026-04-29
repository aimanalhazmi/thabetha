from __future__ import annotations

from fastapi import HTTPException, status

from app.services.ai.transcribe import TranscriptionProvider, TranscriptionResult


class MockTranscriptionProvider(TranscriptionProvider):
    async def transcribe(self, *, content: bytes, file_name: str, content_type: str | None) -> TranscriptionResult:
        text = content.decode("utf-8", errors="ignore").strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "transcription_failed", "message": "Could not transcribe the audio"},
            )
        return TranscriptionResult(raw_transcript=text)
