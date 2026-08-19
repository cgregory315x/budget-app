import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import CategorizationSource


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    posted_date: date
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    excluded_from_budget: bool = False

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("description must not be empty")
        return normalized

    @field_validator("amount")
    @classmethod
    def reject_zero_amount(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("amount must not be zero")
        return value


class TransactionUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    posted_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=500)
    amount: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    excluded_from_budget: bool | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("description must not be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("description must not be empty")
        return normalized

    @field_validator("amount")
    @classmethod
    def reject_invalid_amount(cls, value: Decimal | None) -> Decimal:
        if value is None or value == 0:
            raise ValueError("amount must be nonzero and not null")
        return value

    @model_validator(mode="after")
    def reject_empty_or_null_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        non_nullable = {
            "account_id",
            "posted_date",
            "description",
            "amount",
            "excluded_from_budget",
        }
        for field in self.model_fields_set & non_nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    category_id: uuid.UUID | None
    categorization_source: CategorizationSource | None
    categorization_rule_id: uuid.UUID | None
    posted_date: date
    description: str
    amount: Decimal
    excluded_from_budget: bool
    created_at: datetime
    updated_at: datetime
