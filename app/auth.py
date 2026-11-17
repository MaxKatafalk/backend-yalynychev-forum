from base64 import b64decode
from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .storage import UserStore


password_hasher = PasswordHasher()
dummy_hash = password_hasher.hash(token_urlsafe())


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": "Неверный логин или пароль", "field": "authorization"},
        headers={"WWW-Authenticate": 'Basic realm="forum", charset="UTF-8"'},
    )


class ForumBasicAuth(HTTPBasic):
    async def __call__(self, request: Request) -> HTTPBasicCredentials:
        scheme, _, encoded = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "basic":
            raise unauthorized()
        try:
            decoded = b64decode(encoded, validate=True).decode("utf-8")
        except ValueError:
            raise unauthorized() from None

        username, separator, password = decoded.partition(":")
        if not separator:
            raise unauthorized()
        return HTTPBasicCredentials(username=username, password=password)


basic_auth = ForumBasicAuth()


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(basic_auth),
    db: Session = Depends(get_db),
) -> User:
    user = UserStore(db).get_by_username(credentials.username.strip())
    password_hash = user.password_hash if user is not None else dummy_hash
    try:
        password_hasher.verify(password_hash, credentials.password)
    except (InvalidHashError, VerificationError):
        raise unauthorized() from None
    if user is None:
        raise unauthorized()
    return user
