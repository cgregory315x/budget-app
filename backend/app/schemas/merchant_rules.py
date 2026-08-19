import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.categorization.merchant import normalize_merchant
from app.db.models import RuleMatchType


class MerchantRuleCreate(BaseModel):
    pattern: str = Field(min_length=1, max_length=200)
    match_type: RuleMatchType
    category_id: uuid.UUID
    priority: int = Field(default=100, ge=0, le=10_000)
    enabled: bool = True

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        value = value.strip()
        if not normalize_merchant(value):
            raise ValueError("pattern must contain a letter or number")
        return value


class MerchantRuleUpdate(BaseModel):
    pattern: str | None = Field(default=None, min_length=1, max_length=200)
    match_type: RuleMatchType | None = None
    category_id: uuid.UUID | None = None
    priority: int | None = Field(default=None, ge=0, le=10_000)
    enabled: bool | None = None

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("pattern must not be null")
        value = value.strip()
        if not normalize_merchant(value):
            raise ValueError("pattern must contain a letter or number")
        return value

    @model_validator(mode="after")
    def reject_empty_or_null_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class MerchantRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern: str
    pattern_normalized: str
    match_type: RuleMatchType
    category_id: uuid.UUID
    priority: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CompetingRulePreview(BaseModel):
    rule_id: uuid.UUID
    pattern: str
    match_type: RuleMatchType
    priority: int
    category_id: uuid.UUID
    category_name: str


class RuleMatchPreview(BaseModel):
    transaction_id: uuid.UUID
    account_id: uuid.UUID
    account_name: str
    description: str
    merchant_normalized: str
    posted_date: str
    amount: str
    rule_id: uuid.UUID
    rule_pattern: str
    category_id: uuid.UUID
    category_name: str
    competing_rules: list[CompetingRulePreview]
    conflict_explanation: str | None


class RulePreviewResponse(BaseModel):
    matches: list[RuleMatchPreview]
    unmatched_count: int


class RuleApplyDecision(BaseModel):
    transaction_id: uuid.UUID
    category_id: uuid.UUID
    save_exact_rule: bool = False


class RuleApplyRequest(BaseModel):
    decisions: list[RuleApplyDecision] = Field(min_length=1, max_length=1000)

    @field_validator("decisions")
    @classmethod
    def unique_ids(cls, value: list[RuleApplyDecision]) -> list[RuleApplyDecision]:
        transaction_ids = [decision.transaction_id for decision in value]
        if len(set(transaction_ids)) != len(transaction_ids):
            raise ValueError("decisions must contain unique transaction IDs")
        return value


class RuleApplyResponse(BaseModel):
    applied_count: int
    skipped_count: int
    learned_rule_count: int
