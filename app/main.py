import logging
from time import perf_counter
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import ErrorResponse, HealthResponse, Topic, TopicCreate, TopicListQuery, TopicPatch
from .storage import TopicStore


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("forum.requests")
TopicId = Annotated[int, Path(gt=0, description="Положительный идентификатор темы")]
NOT_FOUND = {"error": "Тема не найдена", "field": "id"}


def validation_message(error: dict) -> str:
    kind = error["type"]
    context = error.get("ctx", {})
    messages = {
        "missing": "Обязательное поле отсутствует",
        "string_type": "Ожидается строка",
        "string_too_short": "Строка не должна быть пустой или состоять из пробелов",
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


def create_app() -> FastAPI:
    application = FastAPI(
        title="Форум — лабораторная 1",
        version="1.0.0",
        description=(
            "CRUD тем форума. Данные хранятся в памяти одного процесса. "
            "Статусы: open — открыта, closed — закрыта. "
        ),
        responses={400: {"model": ErrorResponse, "description": "Ошибка валидации"}},
    )
    application.state.topics = TopicStore()

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
        "/api/topics", response_model=Topic, status_code=status.HTTP_201_CREATED,
        tags=["Темы"], summary="Создать тему",
        responses={201: {"headers": {"Location": {"schema": {"type": "string"}}}}},
    )
    def create_topic(data: TopicCreate, request: Request, response: Response):
        topic = request.app.state.topics.create(data)
        response.headers["Location"] = f"/api/topics/{topic.id}"
        return topic

    @application.get("/api/topics", response_model=list[Topic], tags=["Темы"], summary="Список тем")
    def list_topics(query: Annotated[TopicListQuery, Query()], request: Request):
        """Фильтры объединяются через И; затем применяются offset и limit. Порядок: id по возрастанию."""
        return request.app.state.topics.list(query)

    @application.get(
        "/api/topics/{topic_id}", response_model=Topic, tags=["Темы"], summary="Получить тему",
        responses={404: {"model": ErrorResponse, "description": "Тема не найдена"}},
    )
    def get_topic(topic_id: TopicId, request: Request):
        topic = request.app.state.topics.get(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return topic

    @application.patch(
        "/api/topics/{topic_id}", response_model=Topic, tags=["Темы"], summary="Изменить поля темы",
        responses={404: {"model": ErrorResponse, "description": "Тема не найдена"}},
    )
    def update_topic(topic_id: TopicId, data: TopicPatch, request: Request):
        """Передайте одно или несколько полей. Пропущенные поля сохраняются; null запрещён."""
        topic = request.app.state.topics.update(topic_id, data)
        if topic is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return topic

    @application.delete(
        "/api/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
        tags=["Темы"], summary="Удалить тему",
        responses={404: {"model": ErrorResponse, "description": "Тема не найдена"}},
    )
    def delete_topic(topic_id: TopicId, request: Request):
        if not request.app.state.topics.delete(topic_id):
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

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
