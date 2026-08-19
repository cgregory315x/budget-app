import hashlib
import json
import os
import tempfile
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pdfplumber
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.categorization.merchant import normalize_merchant
from app.core.config import settings
from app.db.models import Account, ImportStatus, StatementImport, Transaction
from app.imports.registry import DEFAULT_ADAPTERS, identify_adapter
from app.imports.types import StatementAdapter, StatementParseError
from app.schemas.imports import (
    CandidateTransactionPreview,
    ParsedStatementPreview,
    StatementDuplicatePreview,
    StatementImportConfirm,
    StatementImportConfirmResponse,
    StatementImportPreview,
    StatementMetadata,
)
from app.services.transactions import build_fingerprint

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


class ImportConfirmationConflictError(ValueError):
    pass


class ImportConfirmationError(ValueError):
    pass


def _require_active_account(session: Session, account_id: uuid.UUID) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFoundError("Account not found")
    if account.archived:
        raise IneligibleAccountError("An active account is required")
    return account


def _get_adapter_by_name(name: str) -> StatementAdapter:
    for adapter in DEFAULT_ADAPTERS:
        if adapter.name == name:
            return adapter
    raise ImportConfirmationError("Statement adapter is not registered")


async def _save_validated_upload(
    upload: UploadFile, path: Path, max_bytes: int
) -> tuple[int, str]:
    if upload.content_type != PDF_CONTENT_TYPE:
        raise InvalidPdfError("File must have the application/pdf MIME type")

    total = 0
    first_bytes = b""
    digest = hashlib.sha256()
    with path.open("wb") as destination:
        while chunk := await upload.read(READ_CHUNK_BYTES):
            if not first_bytes:
                first_bytes = chunk[: len(PDF_SIGNATURE)]
            total += len(chunk)
            if total > max_bytes:
                raise PdfTooLargeError(f"PDF must be no larger than {max_bytes} bytes")
            destination.write(chunk)
            digest.update(chunk)

    if total == 0 or first_bytes != PDF_SIGNATURE:
        raise InvalidPdfError("File does not have a valid PDF signature")
    return total, digest.hexdigest()


def _find_statement_duplicate(
    session: Session, file_sha256: str
) -> StatementDuplicatePreview:
    existing_id = session.scalar(
        select(StatementImport.id).where(StatementImport.file_sha256 == file_sha256)
    )
    return StatementDuplicatePreview(
        is_duplicate=existing_id is not None,
        existing_import_id=existing_id,
    )


def _find_transaction_duplicate(
    candidate: CandidateTransactionPreview,
    existing: list[Transaction],
    account_id: uuid.UUID,
    occurrence: int,
) -> tuple[Literal["exact", "possible"] | None, uuid.UUID | None]:
    normalized = normalize_merchant(candidate.description)
    fingerprint = build_fingerprint(
        account_id,
        candidate.posted_date,
        normalized,
        candidate.amount,
        occurrence,
    )
    possible: Transaction | None = None
    for transaction in existing:
        if (
            transaction.posted_date != candidate.posted_date
            or transaction.amount != candidate.amount
        ):
            continue
        if transaction.fingerprint == fingerprint:
            return "exact", transaction.id
        possible = possible or transaction
    if possible is not None:
        return "possible", possible.id
    return None, None


def _annotate_transaction_duplicates(
    session: Session,
    account_id: uuid.UUID,
    candidates: list[CandidateTransactionPreview],
) -> None:
    existing = list(
        session.scalars(select(Transaction).where(Transaction.account_id == account_id))
    )
    occurrences: dict[tuple[date, str, Decimal], int] = {}
    for candidate in candidates:
        key = (
            candidate.posted_date,
            normalize_merchant(candidate.description),
            candidate.amount,
        )
        occurrences[key] = occurrences.get(key, 0) + 1
        status, matched_id = _find_transaction_duplicate(
            candidate, existing, account_id, occurrences[key]
        )
        candidate.duplicate_status = status
        candidate.matched_transaction_id = matched_id
        if status == "exact":
            candidate.warnings.append("Exact duplicate of an existing transaction")
        elif status == "possible":
            candidate.warnings.append("Possible duplicate: same posted date and amount")


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
    account = _require_active_account(session, account_id)
    upload_limit = settings.statement_upload_max_bytes if max_bytes is None else max_bytes
    file_descriptor, temporary_name = tempfile.mkstemp(suffix=".pdf")
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        size_bytes, file_sha256 = await _save_validated_upload(
            upload, temporary_path, upload_limit
        )
        extracted_text, page_count = _extract_text(temporary_path)
        adapter = identify_adapter(extracted_text)
        if account.account_type != adapter.account_type:
            display_type = adapter.account_type.value.replace("_", " ")
            raise IneligibleAccountError(
                f"An active {display_type} account is required for this statement"
            )
        try:
            parsed = adapter.parse(extracted_text)
            parsed_preview = ParsedStatementPreview(
                institution=parsed.institution,
                account_hint=parsed.account_hint,
                period_start=parsed.period_start,
                period_end=parsed.period_end,
                transactions=[
                    CandidateTransactionPreview(
                        posted_date=row.posted_date,
                        description=row.description,
                        amount=row.amount,
                        source_text=row.source_text,
                        confidence=row.confidence,
                        warnings=list(row.warnings),
                        duplicate_status=None,
                        matched_transaction_id=None,
                    )
                    for row in parsed.transactions
                ],
                warnings=list(parsed.warnings),
            )
            _annotate_transaction_duplicates(
                session, account_id, parsed_preview.transactions
            )
        except StatementParseError as error:
            parsed_preview = ParsedStatementPreview(
                institution="Navy Federal Credit Union",
                account_hint=None,
                period_start=None,
                period_end=None,
                transactions=[],
                warnings=[f"Transaction parser needs review: {error}"],
            )
        return StatementImportPreview(
            account_id=account_id,
            adapter=adapter.name,
            statement=StatementMetadata(
                filename=upload.filename or "statement.pdf",
                content_type=PDF_CONTENT_TYPE,
                size_bytes=size_bytes,
                page_count=page_count,
                text_character_count=len(extracted_text),
                file_sha256=file_sha256,
                duplicate=_find_statement_duplicate(session, file_sha256),
            ),
            parsed_statement=parsed_preview,
            extracted_text=extracted_text,
        )
    finally:
        temporary_path.unlink(missing_ok=True)
        await upload.close()


def confirm_statement_import(
    session: Session, data: StatementImportConfirm
) -> StatementImportConfirmResponse:
    account = _require_active_account(session, data.account_id)
    adapter = _get_adapter_by_name(data.adapter)
    if account.account_type != adapter.account_type:
        display_type = adapter.account_type.value.replace("_", " ")
        raise IneligibleAccountError(
            f"An active {display_type} account is required for this statement"
        )
    if session.scalar(
        select(StatementImport.id).where(StatementImport.file_sha256 == data.file_sha256)
    ) is not None:
        raise ImportConfirmationConflictError("This statement PDF was already imported")

    existing_fingerprints = set(
        session.scalars(
            select(Transaction.fingerprint).where(Transaction.account_id == data.account_id)
        )
    )
    used_fingerprints = set(existing_fingerprints)
    occurrences: dict[tuple[date, str, Decimal], int] = {}
    statement_import = StatementImport(
        account_id=data.account_id,
        adapter=data.adapter,
        file_sha256=data.file_sha256,
        statement_start=data.statement_start,
        statement_end=data.statement_end,
        status=ImportStatus.CONFIRMED,
        warnings=json.dumps(data.warnings) if data.warnings else None,
    )
    session.add(statement_import)
    created: list[Transaction] = []
    try:
        session.flush()
        for candidate in data.candidates:
            normalized = normalize_merchant(candidate.description)
            key = (candidate.posted_date, normalized, candidate.amount)
            occurrence = occurrences.get(key, 0) + 1
            occurrences[key] = occurrence
            fingerprint = build_fingerprint(
                data.account_id,
                candidate.posted_date,
                normalized,
                candidate.amount,
                occurrence,
            )
            if fingerprint in existing_fingerprints and not candidate.allow_duplicate:
                raise ImportConfirmationConflictError(
                    "An approved row exactly matches an existing transaction"
                )
            while fingerprint in used_fingerprints:
                occurrence += 1
                fingerprint = build_fingerprint(
                    data.account_id,
                    candidate.posted_date,
                    normalized,
                    candidate.amount,
                    occurrence,
                )
            used_fingerprints.add(fingerprint)
            transaction = Transaction(
                account_id=data.account_id,
                category_id=None,
                statement_import_id=statement_import.id,
                posted_date=candidate.posted_date,
                description=candidate.description,
                merchant_normalized=normalized,
                amount=candidate.amount,
                fingerprint=fingerprint,
                occurrence_index=occurrence,
                excluded_from_budget=False,
                categorization_confidence=candidate.confidence,
            )
            session.add(transaction)
            created.append(transaction)
        session.commit()
    except ImportConfirmationConflictError:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise ImportConfirmationConflictError(
            "The statement or one of its transactions was already imported"
        ) from error

    return StatementImportConfirmResponse(
        import_id=statement_import.id,
        transaction_ids=[transaction.id for transaction in created],
        transaction_count=len(created),
    )
