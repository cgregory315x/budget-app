import uuid

from pydantic import BaseModel, Field


class StatementMetadata(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = Field(ge=1)
    page_count: int = Field(ge=1)
    text_character_count: int = Field(ge=1)


class StatementImportPreview(BaseModel):
    account_id: uuid.UUID
    adapter: str
    statement: StatementMetadata
    extracted_text: str
