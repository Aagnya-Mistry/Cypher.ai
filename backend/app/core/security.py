from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


@dataclass(slots=True)
class AuthenticatedUser:
    username: str


def require_hardcoded_user(x_api_key: str | None = Header(default=None, alias='x-api-key')) -> AuthenticatedUser:
    settings = get_settings()
    if x_api_key != settings.hardcoded_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )

    return AuthenticatedUser(username=settings.hardcoded_username)
