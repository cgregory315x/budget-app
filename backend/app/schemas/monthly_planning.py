import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def validate_month(value: date) -> date:
    if value.day != 1:
        raise ValueError("month must be the first day of a calendar month")
    return value


class MonthlyBudgetCreate(BaseModel):
    month: date
    category_id: uuid.UUID
    limit_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)

    _validate_month = field_validator("month")(validate_month)


class MonthlyBudgetUpdate(BaseModel):
    month: date | None = None
    category_id: uuid.UUID | None = None
    limit_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )

    @field_validator("month")
    @classmethod
    def validate_optional_month(cls, value: date | None) -> date:
        if value is None:
            raise ValueError("month must not be null")
        return validate_month(value)

    @model_validator(mode="after")
    def reject_empty_or_null_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class MonthlyBudgetResponse(MonthlyBudgetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MonthlyIncomeCreate(BaseModel):
    month: date
    description: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

    _validate_month = field_validator("month")(validate_month)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("description must not be empty")
        return normalized


class MonthlyIncomeUpdate(BaseModel):
    month: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=160)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)

    @field_validator("month")
    @classmethod
    def validate_optional_month(cls, value: date | None) -> date:
        if value is None:
            raise ValueError("month must not be null")
        return validate_month(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("description must not be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("description must not be empty")
        return normalized

    @model_validator(mode="after")
    def reject_empty_or_null_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class MonthlyIncomeResponse(MonthlyIncomeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
