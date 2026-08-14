import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import AccountType


class AccountFields(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    institution: str = Field(min_length=1, max_length=120)
    account_type: AccountType
    currency: str = Field(default="USD", min_length=3, max_length=3)
    current_balance: Decimal | None = Field(
        default=None, max_digits=14, decimal_places=2
    )

    @field_validator("name", "institution")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha() or not normalized.isascii():
            raise ValueError("currency must be a three-letter code")
        return normalized


class AccountCreate(AccountFields):
    pass


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    institution: str | None = Field(default=None, min_length=1, max_length=120)
    account_type: AccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    current_balance: Decimal | None = Field(
        default=None, max_digits=14, decimal_places=2
    )

    @field_validator("name", "institution")
    @classmethod
    def normalize_text(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("value must not be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("account_type")
    @classmethod
    def reject_null_type(cls, value: AccountType | None) -> AccountType:
        if value is None:
            raise ValueError("account_type must not be null")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("currency must not be null")
        normalized = value.upper()
        if not normalized.isalpha() or not normalized.isascii():
            raise ValueError("currency must be a three-letter code")
        return normalized

    @model_validator(mode="after")
    def reject_empty_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class AccountResponse(AccountFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    archived: bool
    created_at: datetime
    updated_at: datetime
