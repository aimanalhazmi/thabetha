from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.datastructures import UploadFile

from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import Repository, get_repository
from app.schemas.domain import MerchantChatOut, MerchantChatRequest, VoiceDebtDraftOut, VoiceDebtDraftRequest
from app.services.ai.draft_extract import extract_voice_debt_draft
from app.services.ai.limits import MERCHANT_CHAT_FEATURE, ensure_ai_quota_available, record_ai_usage
from app.services.ai.merchant_chat import MerchantChatProviderError, run_merchant_chat
from app.services.ai.transcribe import get_transcription_provider, validate_audio_input

router = APIRouter()


def _require_ai_enabled(user: AuthenticatedUser, repo: Repository) -> None:
    profile = repo.ensure_profile(user)
    if not profile.ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ai_subscription_required", "message": "AI features require an active AI subscription"},
        )


def _parse_duration(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_audio_duration", "message": "Invalid audio duration"},
        ) from None


async def _draft_from_json(request: Request, user: AuthenticatedUser, repo: Repository) -> VoiceDebtDraftOut:
    payload = VoiceDebtDraftRequest.model_validate(await request.json())
    profile = repo.ensure_profile(user)
    draft = extract_voice_debt_draft(transcript=payload.transcript, profile=profile)
    record_ai_usage(repo, user.id)
    return draft


async def _draft_from_multipart(request: Request, user: AuthenticatedUser, repo: Repository) -> VoiceDebtDraftOut:
    form = await request.form()
    file = form.get("audio")
    if not isinstance(file, UploadFile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "audio_required", "message": "Audio file is required"},
        )
    file_name = file.filename or "voice-note.webm"
    content_type = file.content_type
    duration = _parse_duration(form.get("client_duration_seconds"))
    validate_audio_input(file_name=file_name, content_type=content_type, client_duration_seconds=duration)

    content = await file.read()
    await file.close()
    storage_path = await repo.save_temp_voice_note(user.id, file_name, content_type, content)
    try:
        result = await get_transcription_provider().transcribe(content=content, file_name=file_name, content_type=content_type)
        profile = repo.ensure_profile(user)
        draft = extract_voice_debt_draft(transcript=result.raw_transcript, profile=profile)
        await repo.delete_temp_voice_note(user.id, storage_path)
        record_ai_usage(repo, user.id)
        return draft
    except Exception:
        await repo.delete_temp_voice_note(user.id, storage_path)
        raise


@router.post("/debt-draft-from-voice", response_model=VoiceDebtDraftOut)
async def draft_debt_from_voice(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> VoiceDebtDraftOut:
    _require_ai_enabled(user, repo)
    ensure_ai_quota_available(repo, user.id)
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        return await _draft_from_multipart(request, user, repo)
    if content_type.startswith("application/json") or not content_type:
        return await _draft_from_json(request, user, repo)
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail={"code": "unsupported_request_type", "message": "Use JSON transcript or multipart audio"},
    )


@router.post("/merchant-chat", response_model=MerchantChatOut)
def merchant_chat(
    payload: MerchantChatRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> MerchantChatOut:
    _require_ai_enabled(user, repo)
    ensure_ai_quota_available(repo, user.id, feature=MERCHANT_CHAT_FEATURE)
    try:
        return run_merchant_chat(repo, user, payload)
    except MerchantChatProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ai_provider_unavailable", "message": str(exc) or "Couldn't reach the assistant"},
        ) from exc
