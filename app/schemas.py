from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from pydantic_core import PydanticCustomError


Title = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)]
Author = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100)]
TopicStatus = Literal["open", "closed"]

class TopicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title = Field(description="Заголовок темы", examples=["Обсуждение Python"])
    author: Author = Field(description="Имя автора", examples=["Иван"])
    status: TopicStatus = Field(default="open", description="Открыта или закрыта")

class TopicPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    author: Author | None = None
    status: TopicStatus | None = None

    @field_validator("title", "author", "status", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise PydanticCustomError("null_not_allowed", "Поле не может быть null")
        return value

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise PydanticCustomError("empty_patch", "Передайте хотя бы одно поле для обновления")
        return self

class Topic(TopicCreate):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int = Field(gt=0, description="Идентификатор, назначенный сервером")

class TopicListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=100, description="Размер страницы")
    offset: int = Field(default=0, ge=0, description="Сколько подходящих тем пропустить")
    author: Author | None = Field(default=None, description="Точное имя автора с учётом регистра")
    status: TopicStatus | None = Field(default=None, description="Фильтр по статусу")

class ErrorResponse(BaseModel):
    error: str
    field: str

class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
