import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class StatementMetadata(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = Field(ge=1)
    page_count: int = Field(ge=1)
    text_character_count: int = Field(ge=1)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate: "StatementDuplicatePreview"


class StatementDuplicatePreview(BaseModel):
    is_duplicate: bool
    existing_import_id: uuid.UUID | None


class CandidateTransactionPreview(BaseModel):
    posted_date: date
    description: str
    amount: Decimal
    source_text: str
    confidence: Decimal = Field(ge=0, le=1)
    warnings: list[str]
    duplicate_status: Literal["exact", "possible"] | None
    matched_transaction_id: uuid.UUID | None


class ParsedStatementPreview(BaseModel):
    institution: str
    account_hint: str | None
    period_start: date | None
    period_end: date | None
    transactions: list[CandidateTransactionPreview]
    warnings: list[str]


class StatementImportPreview(BaseModel):
    account_id: uuid.UUID
    adapter: str
    statement: StatementMetadata
    parsed_statement: ParsedStatementPreview
    extracted_text: str


class StatementImportConfirmCandidate(BaseModel):
    posted_date: date
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    allow_duplicate: bool = False

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


class StatementImportConfirm(BaseModel):
    account_id: uuid.UUID
    adapter: str = Field(min_length=1, max_length=80)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    statement_start: date | None
    statement_end: date | None
    warnings: list[str] = Field(default_factory=list, max_length=100)
    candidates: list[StatementImportConfirmCandidate] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_period(self) -> "StatementImportConfirm":
        if (
            self.statement_start is not None
            and self.statement_end is not None
            and self.statement_start > self.statement_end
        ):
            raise ValueError("statement_start must not be after statement_end")
        return self


class StatementImportConfirmResponse(BaseModel):
    import_id: uuid.UUID
    transaction_ids: list[uuid.UUID]
    transaction_count: int = Field(ge=1)
