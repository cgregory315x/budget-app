import re
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import CategoryKind

_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CategoryFields(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: CategoryKind
    color: str = "#667085"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        if not _COLOR_PATTERN.fullmatch(value):
            raise ValueError("color must be a six-digit hex value")
        return value.upper()


class CategoryCreate(CategoryFields):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: CategoryKind | None = None
    color: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("name must not be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized

    @field_validator("kind")
    @classmethod
    def reject_null_kind(cls, value: CategoryKind | None) -> CategoryKind:
        if value is None:
            raise ValueError("kind must not be null")
        return value

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str | None) -> str:
        if value is None or not _COLOR_PATTERN.fullmatch(value):
            raise ValueError("color must be a six-digit hex value")
        return value.upper()

    @model_validator(mode="after")
    def reject_empty_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class CategoryResponse(CategoryFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    archived: bool
    created_at: datetime
    updated_at: datetime
