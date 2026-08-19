import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class StatementMetadata(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = Field(ge=1)
    page_count: int = Field(ge=1)
    text_character_count: int = Field(ge=1)


class CandidateTransactionPreview(BaseModel):
    posted_date: date
    description: str
    amount: Decimal
    source_text: str
    confidence: Decimal = Field(ge=0, le=1)
    warnings: list[str]


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
