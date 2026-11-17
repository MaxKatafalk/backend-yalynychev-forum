import logging
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import authenticate, create_access_token, get_current_user
from .database import get_db
from .models import Topic as TopicRecord
from .models import User
from .schemas import (
    AccessToken,
    ErrorResponse,
    HealthResponse,
    Message,
    MessageCreate,
    Topic,
    TopicCreate,
    TopicListQuery,
    TopicPatch,
    TopicStats,
    UserLogin,
    UserRegister,
    UserResponse,
)
from .storage import MessageStore, TopicStore, UserStore


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("forum.requests")
TopicId = Annotated[int, Path(gt=0, description="Положительный идентификатор темы")]
NOT_FOUND = {"error": "Тема не найдена", "field": "id"}
FORBIDDEN = {"error": "Изменять или удалять тему может её владелец или администратор", "field": "owner_id"}
CLOSED_TOPIC = {"error": "В закрытую тему нельзя добавлять сообщения", "field": "status"}


def validation_message(error: dict) -> str:
    kind = error["type"]
    context = error.get("ctx", {})
    messages = {
        "missing": "Обязательное поле отсутствует",
        "string_type": "Ожидается строка",
        "string_too_short": "Строка не должна быть пустой или состоять из пробелов",
        "too_short": f"Минимальная длина: {context.get('min_length')} символов",
        "too_long": f"Максимальная длина: {context.get('max_length')} символов",
        "string_pattern_mismatch": "Допустимы латинские буквы, цифры, точка, дефис и подчёркивание",
        "string_too_long": f"Максимальная длина: {context.get('max_length')} символов",
        "literal_error": "Недопустимое значение; ожидается open или closed",
        "extra_forbidden": "Неизвестное поле",
        "int_parsing": "Ожидается целое число",
        "int_type": "Ожидается целое число",
        "greater_than": f"Значение должно быть больше {context.get('gt')}",
        "greater_than_equal": f"Значение должно быть не меньше {context.get('ge')}",
        "less_than_equal": f"Значение должно быть не больше {context.get('le')}",
        "json_invalid": "Некорректный JSON",
        "model_attributes_type": "Тело запроса должно быть JSON-объектом",
        "model_type": "Тело запроса должно быть JSON-объектом",
        "null_not_allowed": "Поле не может быть null",
        "empty_patch": "Передайте хотя бы одно поле для обновления",
    }
    return messages.get(kind, "Некорректное значение")


def get_owned_topic(
    topic_id: TopicId,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TopicRecord:
    db.execute(text("BEGIN IMMEDIATE"))
    topic = TopicStore(db).get(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if topic.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail=FORBIDDEN)
    return topic


def create_app() -> FastAPI:
    application = FastAPI(
        title="Форум — лабораторная 3",
        version="3.0.0",
        description=(
            "CRUD тем форума и сообщения внутри тем. Данные хранятся в SQLite и сохраняются после перезапуска. "
            "Статусы: open — открыта, closed — закрыта. "
        ),
        responses={400: {"model": ErrorResponse, "description": "Ошибка валидации"}},
    )

    @application.middleware("http")
    async def log_request(request: Request, call_next):
        started = perf_counter()
        code = 500
        try:
            response = await call_next(request)
            code = response.status_code
            return response
        finally:
            path = request.url.path
            if request.url.query:
                path += "?" + request.url.query
            logger.info("%s %s %d %.1fms", request.method, path, code, (perf_counter() - started) * 1000)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        location = first.get("loc", ())
        parts = [part for part in location if part not in ("body", "query", "path")]
        field = str(parts[0]) if parts else "body"
        if first["type"] == "json_invalid":
            field = "body"
        return JSONResponse(status_code=400, content={"error": validation_message(first), "field": field})

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if not isinstance(detail, dict) or "error" not in detail:
            detail = {"error": str(detail), "field": "path"}
        return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)

    @application.get("/health", response_model=HealthResponse, tags=["Состояние"], summary="Проверка сервиса")
    def health():
        return HealthResponse()

    @application.post(
        "/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
        tags=["Пользователи"], summary="Зарегистрировать пользователя",
        responses={409: {"model": ErrorResponse, "description": "Логин уже занят"}},
    )
    def register_user(data: UserRegister, db: Session = Depends(get_db)):
        user = UserStore(db).register(data)
        if user is None:
            raise HTTPException(status_code=409, detail={"error": "Логин уже занят", "field": "username"})
        return user

    @application.post(
        "/auth/login", response_model=AccessToken,
        tags=["Пользователи"], summary="Получить JWT",
        responses={
            401: {"model": ErrorResponse, "description": "Не удалось подтвердить вход"},
            429: {"model": ErrorResponse, "description": "Слишком много попыток входа"},
            503: {"model": ErrorResponse, "description": "JWT не настроен"},
        },
    )
    def login(data: UserLogin, request: Request, db: Session = Depends(get_db)):
        user = authenticate(data.username, data.password.get_secret_value(), db, request)
        return AccessToken(access_token=create_access_token(user))

    @application.get(
        "/auth/me", response_model=UserResponse,
        tags=["Пользователи"], summary="Текущий пользователь",
        responses={
            401: {"model": ErrorResponse, "description": "Не удалось подтвердить вход"},
            429: {"model": ErrorResponse, "description": "Слишком много попыток входа"},
        },
    )
    def current_user(user: User = Depends(get_current_user)):
        return user

    @application.post(
        "/api/topics", response_model=Topic, status_code=status.HTTP_201_CREATED,
        tags=["Темы"], summary="Создать тему",
        responses={
            201: {"headers": {"Location": {"schema": {"type": "string"}}}},
            401: {"model": ErrorResponse, "description": "Требуется вход"},
            429: {"model": ErrorResponse, "description": "Слишком много попыток входа"},
        },
    )
    def create_topic(
        data: TopicCreate, response: Response,
        user: User = Depends(get_current_user), db: Session = Depends(get_db),
    ):
        topic = TopicStore(db).create(data, user.id)
        response.headers["Location"] = f"/api/topics/{topic.id}"
        return topic

    @application.get("/api/topics", response_model=list[Topic], tags=["Темы"], summary="Список тем")
    def list_topics(query: Annotated[TopicListQuery, Query()], db: Session = Depends(get_db)):
        return TopicStore(db).list(query)

    @application.get(
        "/api/topics/stats", response_model=list[TopicStats],
        tags=["Темы"], summary="Темы по количеству сообщений",
    )
    def topic_stats(db: Session = Depends(get_db)):
        return TopicStore(db).stats()

    @application.get(
        "/api/topics/{topic_id}", response_model=Topic, tags=["Темы"], summary="Получить тему",
        responses={404: {"model": ErrorResponse, "description": "Тема не найдена"}},
    )
    def get_topic(topic_id: TopicId, db: Session = Depends(get_db)):
        topic = TopicStore(db).get(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return topic

    @application.patch(
        "/api/topics/{topic_id}", response_model=Topic, tags=["Темы"], summary="Изменить поля темы",
        responses={
            401: {"model": ErrorResponse, "description": "Требуется вход"},
            429: {"model": ErrorResponse, "description": "Слишком много попыток входа"},
            403: {"model": ErrorResponse, "description": "У пользователя нет прав на эту тему"},
            404: {"model": ErrorResponse, "description": "Тема не найдена"},
        },
    )
    def update_topic(data: TopicPatch, topic: TopicRecord = Depends(get_owned_topic), db: Session = Depends(get_db)):
        return TopicStore(db).update(topic, data)

    @application.delete(
        "/api/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
        tags=["Темы"], summary="Удалить тему",
        responses={
            401: {"model": ErrorResponse, "description": "Требуется вход"},
            429: {"model": ErrorResponse, "description": "Слишком много попыток входа"},
            403: {"model": ErrorResponse, "description": "У пользователя нет прав на эту тему"},
            404: {"model": ErrorResponse, "description": "Тема не найдена"},
        },
    )
    def delete_topic(topic: TopicRecord = Depends(get_owned_topic), db: Session = Depends(get_db)):
        TopicStore(db).delete(topic)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.post(
        "/api/topics/{topic_id}/messages", response_model=Message, status_code=status.HTTP_201_CREATED,
        tags=["Сообщения"], summary="Создать сообщение в теме",
        responses={
            401: {"model": ErrorResponse, "description": "Требуется вход"},
            429: {"model": ErrorResponse, "description": "Слишком много попыток входа"},
            404: {"model": ErrorResponse, "description": "Тема не найдена"},
            409: {"model": ErrorResponse, "description": "Тема закрыта"},
        },
    )
    def create_message(
        topic_id: TopicId, data: MessageCreate,
        user: User = Depends(get_current_user), db: Session = Depends(get_db),
    ):
        db.execute(text("BEGIN IMMEDIATE"))
        topic = TopicStore(db).get(topic_id)
        if topic is None:
            db.rollback()
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        if topic.status == "closed":
            db.rollback()
            raise HTTPException(status_code=409, detail=CLOSED_TOPIC)
        return MessageStore(db).create(topic_id, data, user.id)

    @application.get(
        "/api/topics/{topic_id}/messages", response_model=list[Message],
        tags=["Сообщения"], summary="Список сообщений темы",
        responses={404: {"model": ErrorResponse, "description": "Тема не найдена"}},
    )
    def list_messages(topic_id: TopicId, db: Session = Depends(get_db)):
        if TopicStore(db).get(topic_id) is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return MessageStore(db).list(topic_id)

    def custom_openapi():
        if application.openapi_schema is None:
            schema = get_openapi(
                title=application.title, version=application.version,
                description=application.description, routes=application.routes,
            )
            for path in schema["paths"].values():
                for operation in path.values():
                    if isinstance(operation, dict):
                        operation.get("responses", {}).pop("422", None)
            application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = custom_openapi
    return application


app = create_app()
