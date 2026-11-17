from base64 import b64decode
from datetime import datetime, timezone
from os import getenv
from secrets import token_urlsafe

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .storage import UserStore


password_hasher = PasswordHasher()
dummy_hash = password_hasher.hash(token_urlsafe())
JWT_SECRET = getenv("JWT_SECRET", "")
JWT_TTL_SECONDS = int(getenv("JWT_TTL_SECONDS", "3600"))
JWT_ALGORITHM = "HS256"

if JWT_TTL_SECONDS < 1:
    raise ValueError("JWT_TTL_SECONDS должен быть положительным целым числом")


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": "Неверный логин или пароль", "field": "authorization"},
        headers={"WWW-Authenticate": 'Basic realm="forum", charset="UTF-8"'},
    )


class ForumBasicAuth(HTTPBasic):
    async def __call__(self, request: Request) -> HTTPBasicCredentials | None:
        scheme, _, encoded = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "basic":
            return None
        try:
            decoded = b64decode(encoded, validate=True).decode("utf-8")
        except ValueError:
            raise unauthorized() from None

        username, separator, password = decoded.partition(":")
        if not separator:
            raise unauthorized()
        return HTTPBasicCredentials(username=username, password=password)


basic_auth = ForumBasicAuth(auto_error=False)
bearer_auth = HTTPBearer(auto_error=False, bearerFormat="JWT")


def authenticate(username: str, password: str, db: Session) -> User:
    user = UserStore(db).get_by_username(username.strip())
    password_hash = user.password_hash if user is not None else dummy_hash
    try:
        password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        raise unauthorized() from None
    if user is None:
        raise unauthorized()
    return user


def jwt_secret() -> str:
    if len(JWT_SECRET.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail={"error": "Настройте JWT_SECRET длиной не менее 32 байт", "field": "authorization"},
        )
    return JWT_SECRET


def create_access_token(user: User) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {"sub": str(user.id), "iat": now, "exp": now + JWT_TTL_SECONDS}
    return jwt.encode(claims, jwt_secret(), algorithm=JWT_ALGORITHM)


def invalid_token() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": "Недействительный или просроченный токен", "field": "authorization"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def user_from_token(token: str, db: Session) -> User:
    try:
        claims = jwt.decode(
            token, jwt_secret(), algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise invalid_token() from None

    if not 0 < user_id < 2**63:
        raise invalid_token()
    user = db.get(User, user_id)
    if user is None:
        raise invalid_token()
    return user


def get_current_user(
    basic: HTTPBasicCredentials | None = Depends(basic_auth),
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
    db: Session = Depends(get_db),
) -> User:
    if basic is not None:
        return authenticate(basic.username, basic.password, db)
    if bearer is not None:
        return user_from_token(bearer.credentials, db)
    raise unauthorized()
