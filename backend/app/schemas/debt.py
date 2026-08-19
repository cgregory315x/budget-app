import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoanTermsFields(BaseModel):
    account_id: uuid.UUID
    principal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    annual_rate_basis_points: int = Field(ge=0)
    minimum_payment: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    term_months: int | None = Field(default=None, gt=0)


class LoanTermsCreate(LoanTermsFields):
    pass


class LoanTermsUpdate(BaseModel):
    principal: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    annual_rate_basis_points: int | None = Field(default=None, ge=0)
    minimum_payment: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    term_months: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def reject_empty_or_null_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if field != "term_months" and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class LoanTermsResponse(LoanTermsFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LoanBalanceFields(BaseModel):
    as_of_date: date
    balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    source: str = Field(default="manual", min_length=1, max_length=80)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source must not be empty")
        return normalized


class LoanBalanceCreate(LoanBalanceFields):
    pass


class LoanBalanceUpdate(BaseModel):
    as_of_date: date | None = None
    balance: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    source: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("source must not be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("source must not be empty")
        return normalized

    @model_validator(mode="after")
    def reject_empty_or_null_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class LoanBalanceResponse(LoanBalanceFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    loan_terms_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
