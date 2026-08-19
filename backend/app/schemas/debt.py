import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.debt import PayoffStrategy


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


class ProjectionAssumptions(BaseModel):
    apr_treatment: str
    periodic_rate: str
    compounding: str
    payment_timing: str
    currency_rounding: str
    final_payment: str
    maximum_months: int
    disclaimer: str


class AmortizationProjectionRequest(BaseModel):
    principal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    annual_rate_basis_points: int = Field(ge=0)
    monthly_payment: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    first_payment_date: date
    max_months: int = Field(default=1200, ge=1, le=1200)


class AmortizationPaymentResponse(BaseModel):
    month: int
    payment_date: date
    starting_balance: Decimal
    interest: Decimal
    payment: Decimal
    principal: Decimal
    ending_balance: Decimal


class AmortizationProjectionResponse(BaseModel):
    assumptions: ProjectionAssumptions
    payments: list[AmortizationPaymentResponse]
    total_interest: Decimal
    total_paid: Decimal
    months: int
    payoff_date: date | None
    annual_rate_basis_points: int
    monthly_rate: Decimal


class ScenarioDebtRequest(BaseModel):
    debt_id: uuid.UUID
    balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    annual_rate_basis_points: int = Field(ge=0)
    minimum_payment: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class ScenarioProjectionRequest(BaseModel):
    debts: list[ScenarioDebtRequest] = Field(min_length=1)
    strategies: list[PayoffStrategy] = Field(
        default_factory=lambda: [PayoffStrategy.SNOWBALL, PayoffStrategy.AVALANCHE],
        min_length=1,
    )
    custom_order: list[uuid.UUID] | None = None
    extra_monthly_payment: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2
    )
    first_payment_date: date
    max_months: int = Field(default=1200, ge=1, le=1200)

    @model_validator(mode="after")
    def validate_strategy_selection(self) -> Self:
        if len(set(self.strategies)) != len(self.strategies):
            raise ValueError("each strategy may be requested only once")
        has_custom = PayoffStrategy.CUSTOM in self.strategies
        if has_custom and self.custom_order is None:
            raise ValueError("custom_order is required for the custom strategy")
        if not has_custom and self.custom_order is not None:
            raise ValueError("custom_order requires the custom strategy")
        return self


class ScenarioDebtPaymentResponse(BaseModel):
    debt_id: uuid.UUID
    starting_balance: Decimal
    interest: Decimal
    minimum_payment: Decimal
    strategy_payment: Decimal
    total_payment: Decimal
    principal: Decimal
    ending_balance: Decimal


class ScenarioMonthResponse(BaseModel):
    month: int
    payment_date: date
    extra_payment_targets: list[uuid.UUID]
    payments: list[ScenarioDebtPaymentResponse]
    total_payment: Decimal
    remaining_balance: Decimal


class ScenarioResultResponse(BaseModel):
    strategy: PayoffStrategy
    payoff_order: list[uuid.UUID]
    extra_monthly_payment: Decimal
    monthly_payment_budget: Decimal
    schedule: list[ScenarioMonthResponse]
    total_interest: Decimal
    total_paid: Decimal
    months: int
    payoff_date: date | None
    months_saved: int
    interest_saved: Decimal


class ScenarioComparisonResponse(BaseModel):
    assumptions: ProjectionAssumptions
    comparison_baseline: PayoffStrategy
    scenarios: list[ScenarioResultResponse]
