from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import Response

from app.repositories.local_receipt_store import get_local_receipt

router = APIRouter()


@router.get("/receipt-files/{token}/{filename}")
def get_receipt_file(
    token: Annotated[str, Path(min_length=1)],
    filename: Annotated[str, Path(min_length=1)],
) -> Response:
    receipt = get_local_receipt(token)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt link is invalid or expired")
    return Response(
        content=receipt.content,
        media_type=receipt.content_type,
        headers={"Content-Disposition": f'inline; filename="{receipt.filename or filename}"'},
    )
