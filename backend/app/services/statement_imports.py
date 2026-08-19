import os
import tempfile
import uuid
from pathlib import Path

import pdfplumber
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Account, AccountType
from app.imports.registry import identify_adapter
from app.schemas.imports import StatementImportPreview, StatementMetadata

PDF_CONTENT_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"
READ_CHUNK_BYTES = 64 * 1024


class ImportPreviewError(ValueError):
    """Base class for safe, user-facing import preview failures."""


class AccountNotFoundError(ImportPreviewError):
    pass


class IneligibleAccountError(ImportPreviewError):
    pass


class InvalidPdfError(ImportPreviewError):
    pass


class PdfTooLargeError(ImportPreviewError):
    pass


class EmptyStatementTextError(ImportPreviewError):
    pass


def _require_active_checking_account(session: Session, account_id: uuid.UUID) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFoundError("Account not found")
    if account.archived or account.account_type != AccountType.CHECKING:
        raise IneligibleAccountError("An active checking account is required")
    return account


async def _save_validated_upload(upload: UploadFile, path: Path, max_bytes: int) -> int:
    if upload.content_type != PDF_CONTENT_TYPE:
        raise InvalidPdfError("File must have the application/pdf MIME type")

    total = 0
    first_bytes = b""
    with path.open("wb") as destination:
        while chunk := await upload.read(READ_CHUNK_BYTES):
            if not first_bytes:
                first_bytes = chunk[: len(PDF_SIGNATURE)]
            total += len(chunk)
            if total > max_bytes:
                raise PdfTooLargeError(f"PDF must be no larger than {max_bytes} bytes")
            destination.write(chunk)

    if total == 0 or first_bytes != PDF_SIGNATURE:
        raise InvalidPdfError("File does not have a valid PDF signature")
    return total


def _extract_text(path: Path) -> tuple[str, int]:
    try:
        with pdfplumber.open(path) as pdf:
            page_text = [page.extract_text() or "" for page in pdf.pages]
            page_count = len(pdf.pages)
    except Exception as error:
        # PDF libraries expose several parser-specific exception types. Keep those details
        # behind the API boundary and return one stable validation error.
        raise InvalidPdfError("PDF could not be read") from error

    text = "\n\n".join(page_text).strip()
    if page_count == 0:
        raise InvalidPdfError("PDF must contain at least one page")
    if not text:
        raise EmptyStatementTextError("PDF must contain non-empty selectable text")
    return text, page_count


async def preview_statement_import(
    session: Session,
    account_id: uuid.UUID,
    upload: UploadFile,
    *,
    max_bytes: int | None = None,
) -> StatementImportPreview:
    _require_active_checking_account(session, account_id)
    upload_limit = settings.statement_upload_max_bytes if max_bytes is None else max_bytes
    file_descriptor, temporary_name = tempfile.mkstemp(suffix=".pdf")
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        size_bytes = await _save_validated_upload(upload, temporary_path, upload_limit)
        extracted_text, page_count = _extract_text(temporary_path)
        adapter = identify_adapter(extracted_text)
        return StatementImportPreview(
            account_id=account_id,
            adapter=adapter.name,
            statement=StatementMetadata(
                filename=upload.filename or "statement.pdf",
                content_type=PDF_CONTENT_TYPE,
                size_bytes=size_bytes,
                page_count=page_count,
                text_character_count=len(extracted_text),
            ),
            extracted_text=extracted_text,
        )
    finally:
        temporary_path.unlink(missing_ok=True)
        await upload.close()
