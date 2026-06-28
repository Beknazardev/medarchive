from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_import_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != settings.import_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Invalid or missing API key",
                "details": [],
            },
        )
